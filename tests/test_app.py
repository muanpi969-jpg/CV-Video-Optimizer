"""Regression checks for upload/session handling using Streamlit's app runner."""

import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import streamlit
from streamlit.proto.Common_pb2 import FileURLs
from streamlit.runtime.uploaded_file_manager import UploadedFile, UploadedFileRec
from streamlit.testing.v1 import AppTest

from analysis import VideoInfo
from utils import cleanup_temp_file


APP = Path(__file__).resolve().parents[1] / "app.py"


def upload(file_id):
    return UploadedFile(
        UploadedFileRec(file_id, "video.mp4", "video/mp4", b"x" * 20000),
        FileURLs(),
    )


class UploadStateTests(unittest.TestCase):
    def setUp(self):
        self.app = AppTest.from_file(str(APP), default_timeout=10)
        self.info = VideoInfo(
            duration=60, width=1920, height=1080, fps=30,
            video_bitrate=8000, audio_bitrate=128, total_bitrate=8128,
            file_size_mb=60, codec_video="h264", codec_audio="aac",
            has_audio=True, format_name="mp4", pixel_format="yuv420p",
        )

    def tearDown(self):
        for key in ("input_path", "output_path"):
            if key in self.app.session_state:
                cleanup_temp_file(self.app.session_state[key])

    def run_upload(self, uploaded, info=None, error=None):
        # Streamlit 1.32's AppTest serializes a formatted radio by its label.
        # The browser does this correctly; adapt only the old test runner.
        if streamlit.__version__.startswith("1.32."):
            for radio in self.app.radio:
                if radio.value not in radio.options:
                    radio.set_value(radio.options[0])
        with patch("streamlit.file_uploader", return_value=uploaded), patch(
            "analysis.get_video_info", return_value=info or self.info, side_effect=error
        ) as probe:
            self.app.run()
        self.assertEqual(len(self.app.exception), 0)
        return probe

    def test_empty_app_disables_compression(self):
        self.run_upload(None)
        self.assertTrue(self.app.button[0].disabled)

    def test_replacing_same_filename_analyzes_new_upload(self):
        self.run_upload(upload("first"))
        old_path = self.app.session_state.input_path
        new_info = replace(self.info, duration=90)
        probe = self.run_upload(upload("second"), info=new_info)
        probe.assert_called_once()
        self.assertFalse(Path(old_path).exists())
        self.assertEqual(self.app.session_state.video_info.duration, 90)

    def test_removing_upload_clears_metadata_result_and_temporary_files(self):
        self.run_upload(upload("first"))
        old_path = self.app.session_state.input_path
        self.app.session_state.output_path = old_path
        self.app.session_state.result = {"stale": True}
        self.run_upload(None)
        self.assertFalse(Path(old_path).exists())
        self.assertIsNone(self.app.session_state.video_info)
        self.assertIsNone(self.app.session_state.result)
        self.assertIsNone(self.app.session_state.input_path)
        self.assertTrue(self.app.button[0].disabled)

    def test_failed_analysis_cleans_temp_file_and_keeps_error_on_rerun(self):
        probe = self.run_upload(upload("broken"), error=RuntimeError("Invalid video"))
        self.assertFalse(Path(probe.call_args.args[0]).exists())
        self.assertIn("Invalid video", self.app.error[0].value)
        probe = self.run_upload(upload("broken"))
        probe.assert_not_called()
        self.assertIn("Invalid video", self.app.error[0].value)
        self.assertTrue(self.app.button[0].disabled)

    def test_impossible_target_warns_and_disables_compression(self):
        self.run_upload(upload("long"), info=replace(self.info, duration=3600))
        self.assertIn("too small", self.app.warning[0].value)
        self.assertTrue(self.app.button[0].disabled)


if __name__ == "__main__":
    unittest.main()
