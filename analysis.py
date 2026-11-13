"""
Video Analysis Module
Extracts comprehensive metadata from uploaded video files using FFprobe.
"""

import subprocess
import json
import os
import math
from typing import Optional
from dataclasses import dataclass


@dataclass
class VideoInfo:
    """Structured container for video metadata."""
    duration: float          # seconds
    width: int
    height: int
    fps: float
    video_bitrate: int       # kbps
    audio_bitrate: int       # kbps
    total_bitrate: int       # kbps
    file_size_mb: float
    codec_video: str
    codec_audio: str
    has_audio: bool
    format_name: str
    pixel_format: str


def _positive_number(value, default: float = 0.0) -> float:
    """Read optional FFprobe numbers, which may be null or the string N/A."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) and number > 0 else default


def _frame_rate(value) -> float:
    try:
        numerator, separator, denominator = str(value).partition("/")
        rate = float(numerator) / float(denominator) if separator else float(numerator)
    except (ValueError, ZeroDivisionError):
        return 0.0
    return rate if math.isfinite(rate) and rate > 0 else 0.0


def get_video_info(filepath: str) -> Optional[VideoInfo]:
    """
    Extract full video metadata using FFprobe.
    Raises an error if the file cannot be analyzed or has no usable video duration.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Video file not found: {filepath}")

    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        filepath
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode != 0:
            raise RuntimeError(f"FFprobe failed: {result.stderr}")

        data = json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        raise RuntimeError("FFprobe timed out — file may be corrupted.")
    except json.JSONDecodeError:
        raise RuntimeError("Could not parse FFprobe output.")

    # Parse streams
    video_stream = None
    audio_stream = None

    for stream in data.get("streams", []):
        codec_type = stream.get("codec_type", "")
        if codec_type == "video" and video_stream is None:
            video_stream = stream
        elif codec_type == "audio" and audio_stream is None:
            audio_stream = stream

    if video_stream is None:
        raise ValueError("No video stream found in file.")

    fmt = data.get("format") or {}
    file_size_bytes = int(_positive_number(fmt.get("size"), os.path.getsize(filepath)))
    duration = _positive_number(fmt.get("duration")) or _positive_number(video_stream.get("duration"))
    if not duration:
        raise ValueError("Video duration is missing or invalid; cannot calculate a target bitrate.")
    total_bitrate = int(_positive_number(fmt.get("bit_rate"), file_size_bytes * 8 / duration) / 1000)

    width = int(_positive_number(video_stream.get("width")))
    height = int(_positive_number(video_stream.get("height")))
    if width < 2 or height < 2:
        raise ValueError("Video dimensions are missing or invalid.")

    # Average rate describes playback for variable-frame-rate recordings.
    fps = (_frame_rate(video_stream.get("avg_frame_rate"))
           or _frame_rate(video_stream.get("r_frame_rate"))
           or 30.0)

    has_audio = audio_stream is not None
    audio_bitrate_kbps = 0
    codec_audio = "none"
    if has_audio:
        audio_bitrate_kbps = int(_positive_number(audio_stream.get("bit_rate"), 128000) / 1000)
        codec_audio = audio_stream.get("codec_name", "unknown")

    # Streams in some containers omit bitrates. Deduct audio only when present.
    video_bitrate_kbps = int(_positive_number(video_stream.get("bit_rate")) / 1000)
    if video_bitrate_kbps == 0:
        video_bitrate_kbps = max(0, total_bitrate - audio_bitrate_kbps)

    return VideoInfo(
        duration=duration,
        width=width,
        height=height,
        fps=fps,
        video_bitrate=video_bitrate_kbps,
        audio_bitrate=audio_bitrate_kbps,
        total_bitrate=total_bitrate,
        file_size_mb=file_size_bytes / (1024 * 1024),
        codec_video=video_stream.get("codec_name", "unknown"),
        codec_audio=codec_audio,
        has_audio=has_audio,
        format_name=fmt.get("format_name", "unknown"),
        pixel_format=video_stream.get("pix_fmt", "yuv420p"),
    )


def estimate_output_size_mb(
    duration: float,
    video_bitrate_kbps: int,
    audio_bitrate_kbps: int
) -> float:
    """
    Estimate output file size in MB given bitrates and duration.
    Formula: (video_kbps + audio_kbps) * 1000 * duration_seconds / 8 / 1024**2
    """
    total_kbps = video_bitrate_kbps + audio_bitrate_kbps
    size_bytes = (total_kbps * 1000 * duration) / 8
    return size_bytes / (1024 * 1024)


def calculate_optimal_bitrates(
    video_info: VideoInfo,
    target_size_mb: float,
    mode: str = "balanced"
) -> dict:
    """
    Calculate optimal video and audio bitrates to hit the target size.
    Includes target_feasible and minimum_target_size_mb so callers can reject
    targets below the minimum video/audio budget instead of promising an oversize file.
    """
    if not _positive_number(video_info.duration):
        raise ValueError("Video duration must be finite and greater than zero.")
    if not _positive_number(target_size_mb):
        raise ValueError("Target size must be finite and greater than zero.")
    if video_info.width < 2 or video_info.height < 2:
        raise ValueError("Video dimensions must be at least 2 by 2 pixels.")

    # Audio bitrate by mode
    audio_bitrate_map = {
        "maximum_quality": 192,
        "balanced": 128,
        "smallest_file": 96,
        "rssp_optimized": 128,
    }
    audio_bitrate = audio_bitrate_map.get(mode, 128) if video_info.has_audio else 0

    # Apply 97% of target to leave headroom for container overhead
    usable_size_mb = target_size_mb * 0.97
    total_bits = usable_size_mb * 1024 * 1024 * 8
    audio_bits = audio_bitrate * 1000 * video_info.duration
    video_bits = total_bits - audio_bits
    video_bitrate_kbps = int(video_bits / video_info.duration / 1000)
    minimum_target_size_mb = estimate_output_size_mb(video_info.duration, 300, audio_bitrate) / 0.97
    target_feasible = target_size_mb >= minimum_target_size_mb

    # --- Resolution scaling strategy ---
    width = video_info.width
    height = video_info.height
    fps = _positive_number(video_info.fps, 30.0)
    scale = None  # None = no rescaling

    # Minimum acceptable video bitrates (kbps) per resolution
    quality_floors = {
        "maximum_quality": {2160: 8000, 1440: 5000, 1080: 3000, 720: 1500, 480: 800},
        "balanced":        {2160: 5000, 1440: 3000, 1080: 1500, 720:  900, 480: 500},
        "smallest_file":   {2160: 3000, 1440: 2000, 1080:  800, 720:  500, 480: 300},
        "rssp_optimized":  {2160: 5000, 1440: 3000, 1080: 1500, 720:  900, 480: 500},
    }
    floors = quality_floors.get(mode, quality_floors["balanced"])

    def current_floor(target_height):
        if target_height >= 2160: return floors[2160]
        if target_height >= 1440: return floors[1440]
        if target_height >= 1080: return floors[1080]
        if target_height >= 720: return floors[720]
        return floors[480]

    # Reassess the quality floor at each tier and stop once the budget fits.
    target_h = height
    while video_bitrate_kbps < current_floor(target_h) and target_h > 360:
        target_h = next(tier for tier in (2160, 1440, 1080, 720, 480, 360) if tier < target_h)

    if target_h != height:
        # Calculate proportional width (keep aspect ratio, ensure even numbers)
        ratio = target_h / height
        target_w = int(width * ratio)
        target_w = max(2, target_w - target_w % 2)
        scale = f"{target_w}:{target_h}"

    # FPS: reduce to 30 if original is higher, for file size savings
    fps_modes = {
        "maximum_quality": fps,
        "balanced": min(fps, 30),
        "smallest_file": min(fps, 24),
        "rssp_optimized": min(fps, 30),
    }
    target_fps = fps_modes.get(mode, min(fps, 30))

    # Clamp bitrate to sensible range
    video_bitrate_kbps = max(300, min(video_bitrate_kbps, 20000))

    return {
        "video_bitrate": video_bitrate_kbps,
        "audio_bitrate": audio_bitrate,
        "scale": scale,
        "fps": target_fps,
        "target_feasible": target_feasible,
        "minimum_target_size_mb": minimum_target_size_mb,
        "estimated_size_mb": estimate_output_size_mb(
            video_info.duration, video_bitrate_kbps, audio_bitrate
        ),
    }
