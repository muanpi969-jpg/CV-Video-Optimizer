import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from analysis import VideoInfo, get_video_info
from compression import compress_video


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg is required")
class CompressionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def ffmpeg(self, *args):
        subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *map(str, args)],
            check=True, capture_output=True, timeout=30,
        )

    def decode(self, path):
        self.ffmpeg("-i", path, "-f", "null", "-")

    def test_two_pass_uses_analyzed_streams_and_reports_overall_progress(self):
        source = self.root / "multiple-tracks.mkv"
        output = self.root / "output.mp4"
        self.ffmpeg(
            "-f", "lavfi", "-i", "testsrc2=size=320x240:rate=24",
            "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=24",
            "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100",
            "-t", "3", "-map", "0:v", "-map", "1:v", "-map", "2:a",
            "-c:v", "libx264", "-threads", "2", "-preset", "ultrafast", "-c:a", "aac", source,
        )
        source_info = get_video_info(str(source))
        self.assertEqual((source_info.width, source_info.height), (320, 240))
        progress = []
        result = compress_video(
            str(source), str(output), source_info, 0.3, "balanced",
            lambda value, stage: progress.append(value),
        )
        actual = get_video_info(str(output))
        self.assertEqual((actual.width, actual.height), (320, 240))
        self.assertEqual((actual.codec_video, actual.codec_audio), ("h264", "aac"))
        self.assertAlmostEqual(actual.duration, source_info.duration, delta=0.2)
        self.assertTrue(result["under_target"])
        self.assertEqual(progress, sorted(progress))
        self.assertEqual((progress[0], progress[-1]), (0.0, 1.0))
        self.decode(output)

    def test_odd_silent_video_and_mp4_directory(self):
        source = self.root / "odd.mkv"
        directory = self.root / "folder.mp4"
        directory.mkdir()
        output = directory / "OUTPUT.MP4"
        self.ffmpeg(
            "-f", "lavfi", "-i", "testsrc=size=321x241:rate=24", "-t", "2",
            "-c:v", "libx264", "-threads", "2", "-pix_fmt", "yuv444p", source,
        )
        info = get_video_info(str(source))
        result = compress_video(str(source), str(output), info, 0.2, "balanced")
        actual = get_video_info(str(output))
        self.assertEqual((actual.width, actual.height), (322, 242))
        self.assertEqual(actual.pixel_format, "yuv420p")
        self.assertFalse(actual.has_audio)
        self.assertTrue(result["under_target"])
        self.assertEqual(list(directory.iterdir()), [output])
        self.decode(output)

    def test_failed_encoding_preserves_diagnostics_and_cleans_logs(self):
        source = self.root / "input.mp4"
        self.ffmpeg(
            "-f", "lavfi", "-i", "testsrc2=size=320x240:rate=24", "-t", "1",
            "-c:v", "libx264", "-threads", "2", source,
        )
        info = get_video_info(str(source))
        missing = self.root / "missing.mp4"
        temporary_directory = tempfile.TemporaryDirectory
        with patch(
            "compression.tempfile.TemporaryDirectory",
            side_effect=lambda **kwargs: temporary_directory(dir=self.root, **kwargs),
        ):
            with self.assertRaisesRegex(RuntimeError, "No such file or directory"):
                compress_video(str(missing), str(self.root / "output.mp4"), info, 0.2, "balanced")
        self.assertFalse(list(self.root.glob("svcv_pass_*")))

    def test_rejects_impossible_target_before_starting_encoder(self):
        info = VideoInfo(
            duration=600, width=640, height=360, fps=24,
            video_bitrate=1000, audio_bitrate=128, total_bitrate=1128,
            file_size_mb=100, codec_video="h264", codec_audio="aac",
            has_audio=True, format_name="mp4", pixel_format="yuv420p",
        )
        with patch("compression.subprocess.Popen") as encoder:
            with self.assertRaisesRegex(ValueError, "Target size is too small"):
                compress_video("input.mp4", "output.mp4", info, 5, "balanced")
            encoder.assert_not_called()

    def test_refuses_to_overwrite_input(self):
        source = self.root / "input.mp4"
        with self.assertRaisesRegex(ValueError, "different files"):
            compress_video(str(source), str(source), None, 20, "balanced")


if __name__ == "__main__":
    unittest.main()
