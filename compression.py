"""
Smart Compression Engine
Handles all FFmpeg-based video compression with intelligent quality optimization.
"""

import subprocess
import math
import os
import re
import tempfile
from collections import deque
from typing import Callable, Optional
from analysis import VideoInfo, calculate_optimal_bitrates


# Quality mode presets — tune FFmpeg parameters per mode
QUALITY_PRESETS = {
    "maximum_quality": {
        "crf": 18,
        "preset": "slow",
        "profile": "high",
        "audio_codec": "aac",
        "description": "Best possible quality. Larger file, slower encode.",
    },
    "balanced": {
        "crf": 23,
        "preset": "medium",
        "profile": "high",
        "audio_codec": "aac",
        "description": "Great quality with good compression. Recommended.",
    },
    "smallest_file": {
        "crf": 28,
        "preset": "fast",
        "profile": "main",
        "audio_codec": "aac",
        "description": "Smallest output. Acceptable quality.",
    },
    "rssp_optimized": {
        "crf": 21,
        "preset": "medium",
        "profile": "high",
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
    video_bitrate_kbps: Optional[int] = None,
) -> list[str]:
    """
    Build a complete FFmpeg command for the given compression settings.
    Supports both single-pass (CRF) and two-pass (target bitrate) encoding.
    """
    preset = QUALITY_PRESETS.get(mode, QUALITY_PRESETS["balanced"])
    bitrates = calculate_optimal_bitrates(video_info, target_size_mb, mode)
    if video_bitrate_kbps is not None:
        bitrates["video_bitrate"] = video_bitrate_kbps

    if two_pass and (pass_num not in (1, 2) or not passlog_prefix):
        raise ValueError("Two-pass encoding requires a pass number and a log prefix.")

    # Match the streams inspected by get_video_info, rather than letting FFmpeg
    # pick a different (for example, higher-resolution) track automatically.
    cmd = ["ffmpeg", "-nostdin", "-y", "-i", input_path, "-map", "0:v:0"]
    if video_info.has_audio and not (two_pass and pass_num == 1):
        cmd += ["-map", "0:a:0"]

    # ── Video filters ──────────────────────────────────────────────────────────
    vf_filters = []

    if bitrates["scale"]:
        # Use Lanczos for high-quality downscaling
        vf_filters.append(f"scale={bitrates['scale']}:flags=lanczos")

    # H.264 with yuv420p requires even dimensions, including when no scaling
    # was needed (screen recordings can have odd widths or heights).
    vf_filters.append("pad=ceil(iw/2)*2:ceil(ih/2)*2")

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
    if os.path.realpath(input_path) == os.path.realpath(output_path):
        raise ValueError("Input and output must be different files.")
    bitrates = calculate_optimal_bitrates(video_info, target_size_mb, mode)
    if not bitrates.get("target_feasible", True):
        raise ValueError(
            "Target size is too small for this video's duration. "
            f"Choose at least {math.ceil(bitrates['minimum_target_size_mb'])} MB."
        )

    def _run(cmd: list, stage: str, offset: float, span: float) -> None:
        """Run FFmpeg, retain diagnostics, and report overall two-pass progress."""
        errors = deque(maxlen=20)
        with subprocess.Popen(
            cmd,
            stderr=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            text=True,
            errors="replace",
            bufsize=1,
        ) as process:
            try:
                duration = video_info.duration
                for line in process.stderr:
                    errors.append(line.rstrip())
                    if progress_callback and "time=" in line:
                        m = re.search(r"time=(\d+):(\d+):([\d.]+)", line)
                        if m:
                            h, mn, seconds = int(m.group(1)), int(m.group(2)), float(m.group(3))
                            elapsed = h * 3600 + mn * 60 + seconds
                            pct = min(max(elapsed / duration, 0.0), 1.0)
                            progress_callback(offset + pct * span, stage)
                process.wait()
            finally:
                # A callback error must not leave an encoder running in the
                # background or block waiting for its stderr pipe to drain.
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
            if process.returncode != 0:
                detail = "\n".join(errors)[-4000:]
                raise RuntimeError(f"FFmpeg failed during {stage}\n{detail}")

    def _encode(video_bitrate: int, progress_start: float, progress_span: float,
                retry: bool = False) -> None:
        # Dedicated logs avoid collisions and work even when a directory or
        # output filename contains '.mp4'. The context cleans every FFmpeg log.
        with tempfile.TemporaryDirectory(prefix="svcv_pass_") as log_dir:
            passlog_prefix = os.path.join(log_dir, "encode")
            half_span = progress_span / 2
            label_prefix = "Size correction — " if retry else ""
            for pass_num, label, offset in (
                (1, "Pass 1: Analysing video...", progress_start),
                (2, "Pass 2: Encoding output...", progress_start + half_span),
            ):
                stage = label_prefix + label
                if progress_callback:
                    progress_callback(offset, stage)
                cmd = build_ffmpeg_command(
                    input_path, output_path, video_info,
                    target_size_mb, mode,
                    two_pass=True, pass_num=pass_num,
                    passlog_prefix=passlog_prefix,
                    video_bitrate_kbps=video_bitrate,
                )
                _run(cmd, stage, offset, half_span)

    initial_bitrate = bitrates["video_bitrate"]
    _encode(initial_bitrate, 0.0, 0.9)

    # Short or unusually complex clips can overshoot x264's requested two-pass
    # bitrate. Retry only on a miss, correcting from the measured output size.
    target_bytes = target_size_mb * 1024 * 1024
    output_bytes = os.path.getsize(output_path) if os.path.isfile(output_path) else 0
    if output_bytes > target_bytes:
        corrected_bitrate = max(
            300,
            int(initial_bitrate * target_bytes / output_bytes * 0.97),
        )
        if corrected_bitrate < initial_bitrate:
            _encode(corrected_bitrate, 0.9, 0.1, retry=True)

    if not os.path.isfile(output_path) or os.path.getsize(output_path) == 0:
        raise RuntimeError("Output file was not created or is empty.")
    if progress_callback:
        progress_callback(1.0, "Compression complete.")

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
