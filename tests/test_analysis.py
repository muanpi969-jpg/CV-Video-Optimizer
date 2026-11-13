import json
import os
import tempfile
import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

from analysis import VideoInfo, calculate_optimal_bitrates, get_video_info


def video_info(**changes):
    info = VideoInfo(
        duration=60, width=1920, height=1080, fps=30,
        video_bitrate=8000, audio_bitrate=128, total_bitrate=8128,
        file_size_mb=60, codec_video="h264", codec_audio="aac",
        has_audio=True, format_name="mp4", pixel_format="yuv420p",
    )
    return replace(info, **changes)


class MetadataTests(unittest.TestCase):
    def setUp(self):
        handle = tempfile.NamedTemporaryFile(delete=False)
        handle.write(b"x" * 1024)
        handle.close()
        self.path = handle.name
        self.addCleanup(os.unlink, self.path)

    def probe(self, video=None, audio=None, fmt=None):
        stream = {"codec_type": "video", "width": 1920, "height": 1080,
                  "r_frame_rate": "30/1", "codec_name": "h264"}
        stream.update(video or {})
        streams = [stream]
        if audio is not None:
            streams.append({"codec_type": "audio", "codec_name": "aac", **audio})
        result = SimpleNamespace(returncode=0, stdout=json.dumps({
            "streams": streams, "format": {"duration": "60", **(fmt or {})}
        }))
        with patch("analysis.subprocess.run", return_value=result):
            return get_video_info(self.path)

    def test_unavailable_metadata_uses_file_and_stream_fallbacks(self):
        info = self.probe(
            video={"bit_rate": "N/A", "duration": "12.5", "avg_frame_rate": "0/0"},
            audio={"bit_rate": None},
            fmt={"duration": "N/A", "size": "N/A", "bit_rate": None},
        )
        self.assertEqual(info.duration, 12.5)
        self.assertEqual(info.file_size_mb, 1024 / (1024 * 1024))
        self.assertEqual(info.audio_bitrate, 128)
        self.assertEqual(info.fps, 30)

    def test_average_frame_rate_preferred_for_variable_rate_input(self):
        info = self.probe(video={"avg_frame_rate": "30000/1001", "r_frame_rate": "60/1"})
        self.assertAlmostEqual(info.fps, 29.97002997)

    def test_invalid_frame_rates_fall_back(self):
        for value in (None, "N/A", "0/0", "NaN", "-10/1", "inf"):
            with self.subTest(value=value):
                info = self.probe(video={"avg_frame_rate": value, "r_frame_rate": value})
                self.assertEqual(info.fps, 30)

    def test_no_audio_is_not_deducted_from_estimated_video_bitrate(self):
        info = self.probe(video={"bit_rate": "N/A"}, fmt={"bit_rate": "2000000"})
        self.assertFalse(info.has_audio)
        self.assertEqual(info.audio_bitrate, 0)
        self.assertEqual(info.video_bitrate, 2000)

    def test_known_audio_is_deducted_from_estimated_video_bitrate(self):
        info = self.probe(audio={"bit_rate": "192000"}, fmt={"bit_rate": "2000000"})
        self.assertEqual(info.video_bitrate, 1808)

    def test_unusable_duration_rejected(self):
        for duration in (None, "N/A", "NaN", "inf", "0", "-1"):
            with self.subTest(duration=duration), self.assertRaisesRegex(ValueError, "duration"):
                self.probe(fmt={"duration": duration})

    def test_unusable_dimensions_rejected(self):
        with self.assertRaisesRegex(ValueError, "dimensions"):
            self.probe(video={"width": "N/A"})


class BitrateTests(unittest.TestCase):
    def test_downscaling_stops_at_first_tier_with_sufficient_budget(self):
        result = calculate_optimal_bitrates(video_info(), 10, "balanced")
        self.assertEqual(result["scale"], "1280:720")
        self.assertTrue(result["target_feasible"])
        self.assertLessEqual(result["estimated_size_mb"], 10 * 0.97)

    def test_4k_downscaling_keeps_1440p_when_budget_allows(self):
        result = calculate_optimal_bitrates(video_info(width=3840, height=2160), 30)
        self.assertEqual(result["scale"], "2560:1440")

    def test_sufficient_budget_preserves_resolution(self):
        self.assertIsNone(calculate_optimal_bitrates(video_info(), 20)["scale"])

    def test_impossible_target_is_explicit(self):
        result = calculate_optimal_bitrates(video_info(duration=600), 5)
        self.assertFalse(result["target_feasible"])
        self.assertGreater(result["minimum_target_size_mb"], 5)
        self.assertEqual(result["video_bitrate"], 300)
        feasible = calculate_optimal_bitrates(video_info(duration=600), result["minimum_target_size_mb"])
        self.assertTrue(feasible["target_feasible"])

    def test_silent_video_spends_no_budget_on_audio(self):
        result = calculate_optimal_bitrates(video_info(has_audio=False), 10)
        self.assertEqual(result["audio_bitrate"], 0)
        self.assertGreater(result["video_bitrate"], calculate_optimal_bitrates(video_info(), 10)["video_bitrate"])

    def test_invalid_inputs_fail_with_clear_errors(self):
        for value in (0, -1, float("nan"), float("inf")):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "duration"):
                    calculate_optimal_bitrates(video_info(duration=value), 20)
                with self.assertRaisesRegex(ValueError, "Target size"):
                    calculate_optimal_bitrates(video_info(), value)


if __name__ == "__main__":
    unittest.main()
