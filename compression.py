"""
Smart Compression Engine
Handles all FFmpeg-based video compression with intelligent quality optimization.
"""

import subprocess
import os
import re
import threading
from typing import Callable, Optional
from analysis import VideoInfo, calculate_optimal_bitrates


# Quality mode presets — tune FFmpeg parameters per mode
QUALITY_PRESETS = {
    "maximum_quality": {
        "crf": 18,
        "preset": "slow",
        "profile": "high",
        "level": "4.1",
        "audio_codec": "aac",
        "description": "Best possible quality. Larger file, slower encode.",
    },
    "balanced": {
        "crf": 23,
        "preset": "medium",
        "profile": "high",
        "level": "4.0",
        "audio_codec": "aac",
        "description": "Great quality with good compression. Recommended.",
    },
    "smallest_file": {
        "crf": 28,
        "preset": "fast",
        "profile": "main",
        "level": "3.1",
        "audio_codec": "aac",
        "description": "Smallest output. Acceptable quality.",
    },
    "rssp_optimized": {
        "crf": 21,
        "preset": "medium",
        "profile": "high",
        "level": "4.0",
        "audio_codec": "aac",
        "description": "Optimized for scholarship/university application videos.",
    },
}


def build_ffmpeg_command(
    input_path: str,
    output_path: str,
    video_info: VideoInfo,
    target_size_mb: float,
    mode: str,
    two_pass: bool = False,
    pass_num: Optional[int] = None,
    passlog_prefix: Optional[str] = None,
) -> list[str]:
    """
    Build a complete FFmpeg command for the given compression settings.
    Supports both single-pass (CRF) and two-pass (target bitrate) encoding.
    """
    preset = QUALITY_PRESETS.get(mode, QUALITY_PRESETS["balanced"])
    bitrates = calculate_optimal_bitrates(video_info, target_size_mb, mode)

    cmd = ["ffmpeg", "-y", "-i", input_path]

    # ── Video filters ──────────────────────────────────────────────────────────
    vf_filters = []

    if bitrates["scale"]:
        # Use Lanczos for high-quality downscaling
        vf_filters.append(f"scale={bitrates['scale']}:flags=lanczos")

    # Normalize FPS
    target_fps = bitrates["fps"]
    if abs(target_fps - video_info.fps) > 0.5:
        vf_filters.append(f"fps={target_fps:.3f}")

    if vf_filters:
        cmd += ["-vf", ",".join(vf_filters)]

    # ── Video codec ────────────────────────────────────────────────────────────
    cmd += [
        "-c:v", "libx264",
        "-profile:v", preset["profile"],
        "-level", preset["level"],
        "-pix_fmt", "yuv420p",
    ]

    if two_pass:
        # Two-pass encoding: precise bitrate targeting
        cmd += ["-b:v", f"{bitrates['video_bitrate']}k"]
        if pass_num == 1:
            cmd += [
                "-pass", "1",
                "-passlogfile", passlog_prefix,
                "-preset", preset["preset"],
                "-an",          # no audio in pass 1
                "-f", "null",
            ]
            if os.name == "nt":  # Windows
                cmd += ["NUL"]
            else:
                cmd += ["/dev/null"]
        else:
            cmd += [
                "-pass", "2",
                "-passlogfile", passlog_prefix,
                "-preset", preset["preset"],
                "-movflags", "+faststart",
            ]
            _add_audio_filters(cmd, video_info, bitrates, preset)
            cmd += [output_path]
    else:
        # Single-pass CRF with maxrate constraint
        maxrate = bitrates["video_bitrate"]
        bufsize = maxrate * 2
        cmd += [
            "-crf", str(preset["crf"]),
            "-maxrate", f"{maxrate}k",
            "-bufsize", f"{bufsize}k",
            "-preset", preset["preset"],
            "-movflags", "+faststart",
        ]
        _add_audio_filters(cmd, video_info, bitrates, preset)
        cmd += [output_path]

    return cmd


def _add_audio_filters(
    cmd: list,
    video_info: VideoInfo,
    bitrates: dict,
    preset: dict,
) -> None:
    """Append audio encoding parameters to the command list."""
    if not video_info.has_audio:
        cmd += ["-an"]
        return

    audio_filters = [
        "loudnorm=I=-16:TP=-1.5:LRA=11",   # EBU R128 loudness normalization
        "highpass=f=80",                       # Remove low-frequency rumble
        "lowpass=f=8000",                      # Keep speech-critical frequencies
    ]

    cmd += [
        "-af", ",".join(audio_filters),
        "-c:a", preset["audio_codec"],
        "-b:a", f"{bitrates['audio_bitrate']}k",
        "-ar", "44100",
        "-ac", "2",
    ]


def compress_video(
    input_path: str,
    output_path: str,
    video_info: VideoInfo,
    target_size_mb: float,
    mode: str,
    progress_callback: Optional[Callable[[float, str], None]] = None,
) -> dict:
    """
    Main compression entry point.
    Uses two-pass encoding for precise size targeting.
    Returns a result dict with output path, sizes, and compression ratio.
    """
    passlog_prefix = output_path.replace(".mp4", "_pass")

    def _run(cmd: list, stage: str) -> None:
        """Run FFmpeg and stream progress updates."""
        process = subprocess.Popen(
            cmd,
            stderr=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )

        duration = video_info.duration
        for line in process.stderr:
            if progress_callback and "time=" in line:
                # Parse elapsed time from FFmpeg output
                m = re.search(r"time=(\d+):(\d+):([\d.]+)", line)
                if m:
                    h, mn, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
                    elapsed = h * 3600 + mn * 60 + s
                    pct = min(elapsed / duration, 1.0) if duration > 0 else 0
                    progress_callback(pct, stage)

        process.wait()
        if process.returncode != 0:
            raise RuntimeError(f"FFmpeg failed during {stage}.")

    try:
        # ── Pass 1 ─────────────────────────────────────────────────────────────
        if progress_callback:
            progress_callback(0.0, "Pass 1: Analysing video...")

        cmd_pass1 = build_ffmpeg_command(
            input_path, output_path, video_info,
            target_size_mb, mode,
            two_pass=True, pass_num=1, passlog_prefix=passlog_prefix
        )
        _run(cmd_pass1, "Pass 1: Analysing video...")

        # ── Pass 2 ─────────────────────────────────────────────────────────────
        if progress_callback:
            progress_callback(0.5, "Pass 2: Encoding output...")

        cmd_pass2 = build_ffmpeg_command(
            input_path, output_path, video_info,
            target_size_mb, mode,
            two_pass=True, pass_num=2, passlog_prefix=passlog_prefix
        )
        _run(cmd_pass2, "Pass 2: Encoding output...")

    finally:
        # Clean up pass log files
        for ext in ["-0.log", "-0.log.mbtree", ".log", ".log.mbtree"]:
            f = passlog_prefix + ext
            if os.path.exists(f):
                try:
                    os.remove(f)
                except OSError:
                    pass

    if not os.path.exists(output_path):
        raise RuntimeError("Output file was not created.")

    output_size_mb = os.path.getsize(output_path) / (1024 * 1024)

    return {
        "output_path": output_path,
        "input_size_mb": video_info.file_size_mb,
        "output_size_mb": output_size_mb,
        "compression_ratio": video_info.file_size_mb / output_size_mb if output_size_mb > 0 else 0,
        "size_reduction_pct": (1 - output_size_mb / video_info.file_size_mb) * 100 if video_info.file_size_mb > 0 else 0,
        "under_target": output_size_mb <= target_size_mb,
    }


def get_ffmpeg_version() -> Optional[str]:
    """Return FFmpeg version string, or None if not installed."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True, text=True, timeout=5
        )
        first_line = result.stdout.splitlines()[0] if result.stdout else ""
        return first_line
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
