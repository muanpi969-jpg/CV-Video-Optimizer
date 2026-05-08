"""
Video Analysis Module
Extracts comprehensive metadata from uploaded video files using FFprobe.
"""

import subprocess
import json
import os
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


def get_video_info(filepath: str) -> Optional[VideoInfo]:
    """
    Extract full video metadata using FFprobe.
    Returns None if the file cannot be analyzed.
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

    fmt = data.get("format", {})
    file_size_bytes = int(fmt.get("size", 0))
    duration = float(fmt.get("duration", 0))
    total_bitrate = int(fmt.get("bit_rate", 0)) // 1000  # convert to kbps

    # Resolution
    width = int(video_stream.get("width", 0))
    height = int(video_stream.get("height", 0))

    # FPS — handle fraction strings like "30000/1001"
    fps_raw = video_stream.get("r_frame_rate", "30/1")
    try:
        if "/" in fps_raw:
            num, den = fps_raw.split("/")
            fps = float(num) / float(den) if float(den) != 0 else 30.0
        else:
            fps = float(fps_raw)
    except (ValueError, ZeroDivisionError):
        fps = 30.0

    # Bitrates
    video_bitrate = int(video_stream.get("bit_rate", 0))
    if video_bitrate == 0 and total_bitrate > 0:
        # Estimate: assume audio is ~128 kbps
        video_bitrate = max(0, (total_bitrate - 128)) * 1000
    video_bitrate_kbps = video_bitrate // 1000

    has_audio = audio_stream is not None
    audio_bitrate_kbps = 0
    codec_audio = "none"

    if has_audio:
        audio_bitrate_raw = int(audio_stream.get("bit_rate", 0))
        audio_bitrate_kbps = audio_bitrate_raw // 1000 if audio_bitrate_raw else 128
        codec_audio = audio_stream.get("codec_name", "unknown")

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
    Formula: (video_kbps + audio_kbps) * duration_seconds / 8 / 1024
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
    Returns a dict with video_bitrate, audio_bitrate, scale, and fps.
    """
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

    # --- Resolution scaling strategy ---
    width = video_info.width
    height = video_info.height
    fps = video_info.fps
    scale = None  # None = no rescaling

    # Minimum acceptable video bitrates (kbps) per resolution
    quality_floors = {
        "maximum_quality": {2160: 8000, 1440: 5000, 1080: 3000, 720: 1500, 480: 800},
        "balanced":        {2160: 5000, 1440: 3000, 1080: 1500, 720:  900, 480: 500},
        "smallest_file":   {2160: 3000, 1440: 2000, 1080:  800, 720:  500, 480: 300},
        "rssp_optimized":  {2160: 5000, 1440: 3000, 1080: 1500, 720:  900, 480: 500},
    }
    floors = quality_floors.get(mode, quality_floors["balanced"])

    def current_floor():
        if height >= 2160: return floors[2160]
        if height >= 1440: return floors[1440]
        if height >= 1080: return floors[1080]
        if height >= 720:  return floors[720]
        return floors[480]

    # Downscale resolution if bitrate is too low for current resolution
    target_h = height
    while video_bitrate_kbps < current_floor() and target_h > 360:
        # Drop to next resolution tier
        if target_h > 1080:
            target_h = 1080
        elif target_h > 720:
            target_h = 720
        elif target_h > 480:
            target_h = 480
        elif target_h > 360:
            target_h = 360
        # Recalculate — lower res can use same bits for better quality
        # (no recalculation needed, but note the new target)

    if target_h != height:
        # Calculate proportional width (keep aspect ratio, ensure even numbers)
        ratio = target_h / height
        target_w = int(width * ratio)
        target_w = target_w if target_w % 2 == 0 else target_w - 1
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
        "estimated_size_mb": estimate_output_size_mb(
            video_info.duration, video_bitrate_kbps, audio_bitrate
        ),
    }
