"""
Utility helpers for the Smart Video CV Optimizer.
Handles temp files, validation, formatting, and cleanup.
"""

import os
import tempfile
import uuid
import shutil
from pathlib import Path
from typing import Optional


ALLOWED_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
MAX_FILE_SIZE_MB = 500


def validate_video_file(uploaded_file) -> tuple[bool, str]:
    """
    Validate an uploaded Streamlit file object.
    Returns (is_valid: bool, message: str).
    """
    if uploaded_file is None:
        return False, "No file uploaded."

    filename = uploaded_file.name.lower()
    ext = Path(filename).suffix

    if ext not in ALLOWED_EXTENSIONS:
        return False, f"Unsupported file type '{ext}'. Please upload MP4 or MOV."

    # Check size (Streamlit file object has .size in bytes)
    size_mb = uploaded_file.size / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        return False, f"File too large ({size_mb:.1f} MB). Maximum is {MAX_FILE_SIZE_MB} MB."

    if size_mb < 0.01:
        return False, "File appears to be empty or corrupted."

    return True, "OK"


def save_upload_to_temp(uploaded_file) -> str:
    """
    Save a Streamlit UploadedFile to a temp file and return the path.
    Caller is responsible for cleanup.
    """
    ext = Path(uploaded_file.name).suffix.lower()
    tmp = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=ext,
        prefix="svcv_input_"
    )
    tmp.write(uploaded_file.getbuffer())
    tmp.flush()
    tmp.close()
    return tmp.name


def make_output_path(input_path: str, suffix: str = "_optimized") -> str:
    """Generate a temp output path for the compressed video."""
    uid = uuid.uuid4().hex[:8]
    tmp_dir = tempfile.gettempdir()
    return os.path.join(tmp_dir, f"svcv_output_{uid}{suffix}.mp4")


def cleanup_temp_file(path: Optional[str]) -> None:
    """Safely delete a temp file if it exists."""
    if path and os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass


def format_filesize(size_mb: float) -> str:
    """Format file size for display."""
    if size_mb >= 1024:
        return f"{size_mb / 1024:.2f} GB"
    if size_mb >= 1:
        return f"{size_mb:.1f} MB"
    return f"{size_mb * 1024:.0f} KB"


def format_duration(seconds: float) -> str:
    """Format duration as MM:SS."""
    m = int(seconds) // 60
    s = int(seconds) % 60
    return f"{m:02d}:{s:02d}"


def format_bitrate(kbps: int) -> str:
    """Format bitrate for display."""
    if kbps >= 1000:
        return f"{kbps / 1000:.1f} Mbps"
    return f"{kbps} kbps"


def format_resolution(width: int, height: int) -> str:
    """Return a human-readable resolution label."""
    if height >= 2160:
        return f"{width}×{height} (4K)"
    if height >= 1440:
        return f"{width}×{height} (2K)"
    if height >= 1080:
        return f"{width}×{height} (1080p)"
    if height >= 720:
        return f"{width}×{height} (720p)"
    return f"{width}×{height}"


def size_color(size_mb: float, target_mb: float) -> str:
    """Return a CSS color string based on how close to the target size we are."""
    ratio = size_mb / target_mb
    if ratio <= 0.85:
        return "#22c55e"   # Green — well under target
    if ratio <= 1.0:
        return "#f59e0b"   # Amber — close to target
    return "#ef4444"       # Red — over target


def check_ffmpeg_installed() -> bool:
    """Return True if FFmpeg is available on PATH."""
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None
