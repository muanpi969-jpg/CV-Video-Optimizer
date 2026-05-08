"""
Smart Video CV Optimizer
A professional-grade video compression tool for scholarship, university,
and job application videos.

Author: Generated for RSSP / Video CV use cases.
"""

import os
import sys
import time
import threading
from pathlib import Path

import streamlit as st

# ── Page config must be FIRST Streamlit call ───────────────────────────────────
st.set_page_config(
    page_title="Smart Video CV Optimizer",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Internal modules ───────────────────────────────────────────────────────────
from analysis import get_video_info, calculate_optimal_bitrates, estimate_output_size_mb
from compression import compress_video, get_ffmpeg_version, QUALITY_PRESETS
from utils import (
    validate_video_file, save_upload_to_temp, make_output_path,
    cleanup_temp_file, format_filesize, format_duration,
    format_bitrate, format_resolution, size_color, check_ffmpeg_installed,
)

# ══════════════════════════════════════════════════════════════════════════════
# GLOBAL CSS
# ══════════════════════════════════════════════════════════════════════════════
CUSTOM_CSS = """
<style>
/* ── Google Fonts ── */
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;500;600;700;800&family=DM+Mono:ital,wght@0,300;0,400;0,500;1,300&display=swap');

/* ── CSS Variables ── */
:root {
    --bg-deep:      #070B14;
    --bg-card:      #0D1220;
    --bg-card2:     #111827;
    --accent:       #00D4FF;
    --accent2:      #6EE7B7;
    --accent3:      #F59E0B;
    --text-primary: #E2E8F0;
    --text-muted:   #64748B;
    --text-dim:     #334155;
    --border:       rgba(0,212,255,0.12);
    --border2:      rgba(255,255,255,0.06);
    --success:      #22C55E;
    --warning:      #F59E0B;
    --danger:       #EF4444;
    --radius:       12px;
    --radius-lg:    20px;
}

/* ── Base ── */
html, body, [class*="css"] {
    font-family: 'Syne', sans-serif !important;
    color: var(--text-primary);
}

.stApp {
    background: var(--bg-deep);
    background-image:
        radial-gradient(ellipse 80% 50% at 50% -20%, rgba(0,212,255,0.08) 0%, transparent 70%),
        radial-gradient(ellipse 60% 40% at 90% 80%, rgba(110,231,183,0.04) 0%, transparent 60%);
}

/* ── Hero header ── */
.hero {
    text-align: center;
    padding: 3rem 2rem 2rem;
    position: relative;
}

.hero-badge {
    display: inline-block;
    background: rgba(0,212,255,0.08);
    border: 1px solid rgba(0,212,255,0.25);
    color: var(--accent);
    font-family: 'DM Mono', monospace;
    font-size: 0.7rem;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    padding: 0.3rem 1rem;
    border-radius: 99px;
    margin-bottom: 1.2rem;
}

.hero-title {
    font-size: clamp(2rem, 5vw, 3.5rem);
    font-weight: 800;
    line-height: 1.05;
    margin: 0 0 1rem;
    background: linear-gradient(135deg, #fff 0%, var(--accent) 50%, var(--accent2) 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}

.hero-sub {
    font-size: 1rem;
    color: var(--text-muted);
    max-width: 480px;
    margin: 0 auto 0.5rem;
    line-height: 1.6;
    font-weight: 400;
}

/* ── Cards ── */
.card {
    background: var(--bg-card);
    border: 1px solid var(--border2);
    border-radius: var(--radius-lg);
    padding: 1.5rem;
    margin-bottom: 1rem;
    position: relative;
    overflow: hidden;
}

.card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 1px;
    background: linear-gradient(90deg, transparent, var(--accent), transparent);
    opacity: 0.3;
}

.card-title {
    font-size: 0.7rem;
    font-family: 'DM Mono', monospace;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--accent);
    margin: 0 0 1.2rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

/* ── Metric pills ── */
.metric-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
    gap: 0.75rem;
    margin-bottom: 0.5rem;
}

.metric-pill {
    background: var(--bg-card2);
    border: 1px solid var(--border2);
    border-radius: var(--radius);
    padding: 0.85rem 1rem;
    text-align: center;
}

.metric-pill .label {
    font-size: 0.65rem;
    font-family: 'DM Mono', monospace;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--text-muted);
    margin-bottom: 0.3rem;
}

.metric-pill .value {
    font-size: 1.05rem;
    font-weight: 700;
    color: var(--text-primary);
}

/* ── Mode selector cards ── */
.mode-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 0.6rem;
}

.mode-card {
    background: var(--bg-card2);
    border: 1.5px solid var(--border2);
    border-radius: var(--radius);
    padding: 0.9rem 1rem;
    cursor: pointer;
    transition: all 0.2s;
}

.mode-card.active {
    border-color: var(--accent);
    background: rgba(0,212,255,0.06);
}

.mode-card .mode-name {
    font-weight: 700;
    font-size: 0.9rem;
    margin-bottom: 0.25rem;
}

.mode-card .mode-desc {
    font-size: 0.72rem;
    color: var(--text-muted);
    line-height: 1.4;
}

/* ── Size display ── */
.size-compare {
    display: flex;
    align-items: center;
    gap: 1rem;
    margin: 1rem 0;
}

.size-box {
    flex: 1;
    background: var(--bg-card2);
    border-radius: var(--radius);
    padding: 1rem;
    text-align: center;
    border: 1px solid var(--border2);
}

.size-box .sz-label {
    font-size: 0.65rem;
    font-family: 'DM Mono', monospace;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--text-muted);
    margin-bottom: 0.4rem;
}

.size-box .sz-value {
    font-size: 1.6rem;
    font-weight: 800;
}

.size-arrow {
    color: var(--accent);
    font-size: 1.5rem;
    flex-shrink: 0;
}

/* ── Progress bar ── */
.progress-wrap {
    background: var(--bg-card2);
    border-radius: 99px;
    height: 6px;
    overflow: hidden;
    margin: 0.5rem 0;
}

.progress-bar {
    height: 100%;
    border-radius: 99px;
    background: linear-gradient(90deg, var(--accent), var(--accent2));
    transition: width 0.3s ease;
}

/* ── Status badges ── */
.badge {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    font-size: 0.72rem;
    font-family: 'DM Mono', monospace;
    padding: 0.2rem 0.7rem;
    border-radius: 99px;
    font-weight: 500;
}

.badge-success {
    background: rgba(34,197,94,0.12);
    color: var(--success);
    border: 1px solid rgba(34,197,94,0.25);
}

.badge-warning {
    background: rgba(245,158,11,0.12);
    color: var(--warning);
    border: 1px solid rgba(245,158,11,0.25);
}

.badge-info {
    background: rgba(0,212,255,0.1);
    color: var(--accent);
    border: 1px solid rgba(0,212,255,0.2);
}

/* ── Reduction stat ── */
.reduction-stat {
    text-align: center;
    padding: 1.5rem;
    background: linear-gradient(135deg, rgba(0,212,255,0.05) 0%, rgba(110,231,183,0.05) 100%);
    border-radius: var(--radius-lg);
    border: 1px solid rgba(0,212,255,0.15);
    margin-bottom: 1rem;
}

.reduction-stat .big-num {
    font-size: 3rem;
    font-weight: 800;
    background: linear-gradient(135deg, var(--accent), var(--accent2));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    line-height: 1;
}

.reduction-stat .big-label {
    font-size: 0.75rem;
    font-family: 'DM Mono', monospace;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: var(--text-muted);
    margin-top: 0.4rem;
}

/* ── FFmpeg missing warning ── */
.ffmpeg-warning {
    background: rgba(245,158,11,0.08);
    border: 1px solid rgba(245,158,11,0.3);
    border-radius: var(--radius);
    padding: 1rem 1.2rem;
    margin-bottom: 1.5rem;
}

/* ── Streamlit overrides ── */
.stFileUploader > div > div {
    border: 2px dashed var(--border) !important;
    border-radius: var(--radius-lg) !important;
    background: rgba(0,212,255,0.02) !important;
    transition: border-color 0.2s !important;
}

.stFileUploader > div > div:hover {
    border-color: var(--accent) !important;
}

div[data-testid="stSlider"] label {
    font-family: 'DM Mono', monospace !important;
    font-size: 0.8rem !important;
    color: var(--text-muted) !important;
    letter-spacing: 0.05em;
}

.stButton > button {
    font-family: 'Syne', sans-serif !important;
    font-weight: 700 !important;
    letter-spacing: 0.04em !important;
    border-radius: 10px !important;
    transition: all 0.2s !important;
}

.stButton > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 8px 25px rgba(0,212,255,0.3) !important;
}

.stDownloadButton > button {
    font-family: 'Syne', sans-serif !important;
    font-weight: 700 !important;
    background: linear-gradient(135deg, var(--accent), var(--accent2)) !important;
    color: #000 !important;
    border: none !important;
    border-radius: 10px !important;
    padding: 0.6rem 2rem !important;
    font-size: 1rem !important;
}

div[data-testid="stSelectbox"] label,
div[data-testid="stRadio"] label {
    font-family: 'DM Mono', monospace !important;
    font-size: 0.75rem !important;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-muted) !important;
}

hr { border-color: var(--border2) !important; }

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
    background: var(--bg-card) !important;
    border-right: 1px solid var(--border2) !important;
}

/* ── Footer ── */
.app-footer {
    text-align: center;
    padding: 2rem 1rem 3rem;
    font-size: 0.72rem;
    font-family: 'DM Mono', monospace;
    color: var(--text-dim);
    letter-spacing: 0.05em;
}

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: var(--bg-deep); }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# SESSION STATE
# ══════════════════════════════════════════════════════════════════════════════
if "video_info" not in st.session_state:
    st.session_state.video_info = None
if "input_path" not in st.session_state:
    st.session_state.input_path = None
if "result" not in st.session_state:
    st.session_state.result = None
if "output_path" not in st.session_state:
    st.session_state.output_path = None
if "last_uploaded_name" not in st.session_state:
    st.session_state.last_uploaded_name = None
if "progress" not in st.session_state:
    st.session_state.progress = 0.0
if "progress_label" not in st.session_state:
    st.session_state.progress_label = ""

# ══════════════════════════════════════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div class="hero">
    <div class="hero-badge">🎬 RSSP · Scholarship · University Applications</div>
    <h1 class="hero-title">Smart Video CV<br>Optimizer</h1>
    <p class="hero-sub">
        Compress 60–90 second application videos to under 20 MB 
        while preserving the highest possible visual and audio quality.
    </p>
</div>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# FFMPEG CHECK
# ══════════════════════════════════════════════════════════════════════════════
ffmpeg_ok = check_ffmpeg_installed()
if not ffmpeg_ok:
    st.markdown("""
    <div class="ffmpeg-warning">
        ⚠️ <strong>FFmpeg not detected.</strong> Please install FFmpeg to use this application.<br>
        <span style="font-size:0.82rem; color:#94a3b8;">
        macOS: <code>brew install ffmpeg</code> &nbsp;·&nbsp;
        Windows: <a href="https://www.gyan.dev/ffmpeg/builds/" target="_blank">Download from gyan.dev</a> &nbsp;·&nbsp;
        Linux: <code>sudo apt install ffmpeg</code>
        </span>
    </div>
    """, unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# LAYOUT: LEFT PANEL | RIGHT PANEL
# ══════════════════════════════════════════════════════════════════════════════
col_left, col_right = st.columns([1, 1], gap="large")

# ─────────────────────────────────────────────────────────────────────────────
# LEFT PANEL: Upload + Analysis
# ─────────────────────────────────────────────────────────────────────────────
with col_left:
    # ── Upload card ──────────────────────────────────────────────────────────
    st.markdown('<div class="card"><div class="card-title">📁 Upload Video</div>', unsafe_allow_html=True)

    uploaded_file = st.file_uploader(
        label="Drag & drop your video here",
        type=["mp4", "mov", "avi", "mkv"],
        help="Supported: MP4, MOV, AVI, MKV — Max 500 MB",
        label_visibility="collapsed",
    )
    st.markdown('</div>', unsafe_allow_html=True)

    # Detect new upload
    if uploaded_file is not None:
        is_new = (uploaded_file.name != st.session_state.last_uploaded_name)

        if is_new:
            # Cleanup previous temp files
            cleanup_temp_file(st.session_state.get("input_path"))
            cleanup_temp_file(st.session_state.get("output_path"))
            st.session_state.video_info = None
            st.session_state.result = None
            st.session_state.output_path = None
            st.session_state.last_uploaded_name = uploaded_file.name

            valid, msg = validate_video_file(uploaded_file)
            if not valid:
                st.error(msg)
            else:
                with st.spinner("Analysing video..."):
                    tmp_path = save_upload_to_temp(uploaded_file)
                    st.session_state.input_path = tmp_path
                    try:
                        info = get_video_info(tmp_path)
                        st.session_state.video_info = info
                    except Exception as e:
                        st.error(f"Could not read video: {e}")

    # ── Video analysis card ──────────────────────────────────────────────────
    info = st.session_state.video_info
    if info:
        st.markdown('<div class="card"><div class="card-title">🔍 Video Analysis</div>', unsafe_allow_html=True)

        resolution_label = format_resolution(info.width, info.height)
        fps_str = f"{info.fps:.2f} fps"
        dur_str = format_duration(info.duration)
        vbr_str = format_bitrate(info.video_bitrate)
        abr_str = format_bitrate(info.audio_bitrate) if info.has_audio else "No audio"
        size_str = format_filesize(info.file_size_mb)

        st.markdown(f"""
        <div class="metric-grid">
            <div class="metric-pill">
                <div class="label">Resolution</div>
                <div class="value">{resolution_label.split(' ')[0]}</div>
            </div>
            <div class="metric-pill">
                <div class="label">Frame Rate</div>
                <div class="value">{fps_str}</div>
            </div>
            <div class="metric-pill">
                <div class="label">Duration</div>
                <div class="value">{dur_str}</div>
            </div>
            <div class="metric-pill">
                <div class="label">File Size</div>
                <div class="value">{size_str}</div>
            </div>
            <div class="metric-pill">
                <div class="label">Video Bitrate</div>
                <div class="value">{vbr_str}</div>
            </div>
            <div class="metric-pill">
                <div class="label">Audio Bitrate</div>
                <div class="value">{abr_str}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Codec info
        st.markdown(f"""
        <div style="margin-top:0.75rem; display:flex; gap:0.5rem; flex-wrap:wrap;">
            <span class="badge badge-info">🎬 {info.codec_video.upper()}</span>
            <span class="badge badge-info">🔊 {info.codec_audio.upper()}</span>
            <span class="badge badge-info">📐 {resolution_label.split('(')[-1].replace(')','') if '(' in resolution_label else 'SD'}</span>
        </div>
        """, unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# RIGHT PANEL: Settings + Compress
# ─────────────────────────────────────────────────────────────────────────────
with col_right:

    info = st.session_state.video_info

    # ── Settings card ────────────────────────────────────────────────────────
    st.markdown('<div class="card"><div class="card-title">⚙️ Compression Settings</div>', unsafe_allow_html=True)

    # Target size slider
    target_size = st.slider(
        "Target file size (MB)",
        min_value=5,
        max_value=100,
        value=20,
        step=1,
        help="The output file will be compressed to stay under this size.",
        disabled=(info is None),
    )

    # Quality mode
    mode_labels = {
        "rssp_optimized": "🎓 RSSP Optimized",
        "maximum_quality": "⚡ Maximum Quality",
        "balanced": "⚖️ Balanced",
        "smallest_file": "🗜️ Smallest File",
    }
    mode_key = st.radio(
        "Quality Mode",
        options=list(mode_labels.keys()),
        format_func=lambda k: mode_labels[k],
        index=0,
        horizontal=False,
        disabled=(info is None),
    )

    # Show mode description
    if info is not None:
        desc = QUALITY_PRESETS[mode_key]["description"]
        st.markdown(
            f'<p style="font-size:0.78rem;color:#64748b;margin:-0.5rem 0 0.5rem;font-family:\'DM Mono\',monospace;">'
            f'→ {desc}</p>',
            unsafe_allow_html=True
        )

    st.markdown('</div>', unsafe_allow_html=True)

    # ── Estimated output card ─────────────────────────────────────────────────
    if info is not None:
        bitrates = calculate_optimal_bitrates(info, target_size, mode_key)
        est_size = bitrates["estimated_size_mb"]
        est_vbr = bitrates["video_bitrate"]
        est_abr = bitrates["audio_bitrate"]
        new_scale = bitrates["scale"]

        color = size_color(est_size, target_size)
        resolution_label = (
            f"→ {new_scale.replace(':', '×')}" if new_scale
            else f"{format_resolution(info.width, info.height)} (unchanged)"
        )

        st.markdown(f"""
        <div class="card">
            <div class="card-title">📊 Estimated Output</div>
            <div class="size-compare">
                <div class="size-box">
                    <div class="sz-label">Original</div>
                    <div class="sz-value" style="color:#94a3b8;">{format_filesize(info.file_size_mb)}</div>
                </div>
                <div class="size-arrow">→</div>
                <div class="size-box">
                    <div class="sz-label">Estimated</div>
                    <div class="sz-value" style="color:{color};">{format_filesize(est_size)}</div>
                </div>
            </div>
            <div style="display:flex; gap:0.5rem; flex-wrap:wrap; margin-top:0.5rem;">
                <span class="badge badge-info">🎬 ~{est_vbr} kbps video</span>
                <span class="badge badge-info">🔊 ~{est_abr} kbps audio</span>
                <span class="badge {'badge-warning' if new_scale else 'badge-success'}">📐 {resolution_label}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ── Compress button ───────────────────────────────────────────────────────
    compress_disabled = (info is None) or (not ffmpeg_ok)
    compress_btn = st.button(
        "🚀  Compress Video",
        use_container_width=True,
        type="primary",
        disabled=compress_disabled,
    )

    # ── Run compression ───────────────────────────────────────────────────────
    if compress_btn and info is not None and ffmpeg_ok:
        output_path = make_output_path(st.session_state.input_path)
        st.session_state.output_path = output_path
        st.session_state.result = None

        progress_bar_placeholder = st.empty()
        status_placeholder = st.empty()

        # Shared state for thread-safe progress updates
        progress_state = {"pct": 0.0, "label": "Initialising…"}
        compress_error = {"msg": None}
        compress_result = {"data": None}

        def progress_callback(pct: float, label: str):
            progress_state["pct"] = pct
            progress_state["label"] = label

        def run_compression():
            try:
                result = compress_video(
                    input_path=st.session_state.input_path,
                    output_path=output_path,
                    video_info=info,
                    target_size_mb=target_size,
                    mode=mode_key,
                    progress_callback=progress_callback,
                )
                compress_result["data"] = result
            except Exception as e:
                compress_error["msg"] = str(e)

        # Run compression in a thread so we can update UI
        t = threading.Thread(target=run_compression, daemon=True)
        t.start()

        while t.is_alive():
            pct = progress_state["pct"]
            lbl = progress_state["label"]
            pct_display = int(pct * 100)

            progress_bar_placeholder.markdown(f"""
            <div style="margin:0.5rem 0;">
                <div style="display:flex; justify-content:space-between; margin-bottom:0.3rem;">
                    <span style="font-size:0.78rem; font-family:'DM Mono',monospace; color:#64748b;">{lbl}</span>
                    <span style="font-size:0.78rem; font-family:'DM Mono',monospace; color:#00D4FF;">{pct_display}%</span>
                </div>
                <div class="progress-wrap">
                    <div class="progress-bar" style="width:{pct_display}%;"></div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            time.sleep(0.5)

        t.join()

        # Show 100%
        progress_bar_placeholder.markdown("""
        <div style="margin:0.5rem 0;">
            <div class="progress-wrap">
                <div class="progress-bar" style="width:100%;"></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        if compress_error["msg"]:
            st.error(f"❌ Compression failed: {compress_error['msg']}")
        elif compress_result["data"]:
            st.session_state.result = compress_result["data"]
            st.rerun()

    # ── Results card ──────────────────────────────────────────────────────────
    result = st.session_state.result
    if result is not None:
        under = result["under_target"]
        reduction = result["size_reduction_pct"]
        ratio = result["compression_ratio"]
        out_size = result["output_size_mb"]
        in_size = result["input_size_mb"]

        badge_html = (
            '<span class="badge badge-success">✅ Under Target</span>'
            if under else
            '<span class="badge badge-warning">⚠️ Slightly Over Target</span>'
        )

        st.markdown(f"""
        <div class="card">
            <div class="card-title">✨ Compression Complete</div>
            <div class="reduction-stat">
                <div class="big-num">{reduction:.0f}%</div>
                <div class="big-label">Size Reduction</div>
            </div>
            <div class="size-compare">
                <div class="size-box">
                    <div class="sz-label">Before</div>
                    <div class="sz-value" style="color:#94a3b8;">{format_filesize(in_size)}</div>
                </div>
                <div class="size-arrow">→</div>
                <div class="size-box">
                    <div class="sz-label">After</div>
                    <div class="sz-value" style="color:{'#22c55e' if under else '#f59e0b'};">{format_filesize(out_size)}</div>
                </div>
            </div>
            <div style="display:flex; gap:0.5rem; flex-wrap:wrap; margin-top:0.5rem; margin-bottom:1rem;">
                {badge_html}
                <span class="badge badge-info">📦 {ratio:.1f}× compression</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Download button
        output_path = st.session_state.output_path
        if output_path and os.path.exists(output_path):
            with open(output_path, "rb") as f:
                file_bytes = f.read()

            original_name = st.session_state.last_uploaded_name or "video"
            stem = Path(original_name).stem
            download_name = f"{stem}_optimized.mp4"

            st.download_button(
                label="⬇️  Download Optimized Video",
                data=file_bytes,
                file_name=download_name,
                mime="video/mp4",
                use_container_width=True,
            )

# ══════════════════════════════════════════════════════════════════════════════
# TIPS SECTION
# ══════════════════════════════════════════════════════════════════════════════
st.divider()

tip_col1, tip_col2, tip_col3 = st.columns(3)

tips = [
    ("🎓", "For RSSP Applications",
     "Use RSSP Optimized mode with 20 MB target. The app will maximize face and speech clarity for academic review panels."),
    ("🎬", "Best Recording Tips",
     "Record in 1080p, good lighting, and quiet environment. Speak clearly at a measured pace. Keep videos under 90 seconds."),
    ("💡", "Quality vs. Size",
     "Two-pass encoding is used automatically for precise size targeting. Maximum Quality mode gives the best looking output within the size budget."),
]

for col, (icon, title, body) in zip([tip_col1, tip_col2, tip_col3], tips):
    with col:
        st.markdown(f"""
        <div class="card" style="height:100%;">
            <div style="font-size:1.8rem; margin-bottom:0.6rem;">{icon}</div>
            <div style="font-weight:700; font-size:0.95rem; margin-bottom:0.5rem;">{title}</div>
            <div style="font-size:0.8rem; color:#64748b; line-height:1.6;">{body}</div>
        </div>
        """, unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# FOOTER
# ══════════════════════════════════════════════════════════════════════════════
ffmpeg_ver = get_ffmpeg_version()
ffmpeg_str = ffmpeg_ver.split("ffmpeg version ")[-1].split(" ")[0] if ffmpeg_ver else "not found"

st.markdown(f"""
<div class="app-footer">
    Smart Video CV Optimizer · Built with FFmpeg {ffmpeg_str} · Streamlit ·
    No data leaves your device · Open source
</div>
""", unsafe_allow_html=True)
