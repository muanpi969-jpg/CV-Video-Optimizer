# 🎬 Smart Video CV Optimizer

> Professional-grade video compression for scholarship, RSSP, and university application videos.  
> Compress 60–90 second videos to **under 20 MB** while preserving maximum visual and audio quality.

---

## ✨ Features

| Feature | Description |
|---|---|
| 🎯 **Target Size Compression** | Set any target size (e.g. 20 MB) — app auto-calculates optimal bitrates |
| 🔍 **Smart Video Analysis** | Resolution, FPS, duration, bitrates detected automatically via FFprobe |
| ⚙️ **4 Quality Modes** | RSSP Optimized · Maximum Quality · Balanced · Smallest File |
| 🎙️ **Audio Optimization** | EBU R128 loudness normalization, speech clarity enhancement |
| 📐 **Smart Resolution Scaling** | Reduces resolution only when necessary to hit the target |
| 🔢 **Two-Pass Encoding** | Precise bitrate targeting for accurate output size |
| 💾 **No Data Leaves Your Device** | All processing is local — no cloud uploads |
| 🌐 **Cross-platform** | macOS · Windows · Linux · Docker |

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.10+**
- **FFmpeg** (must be installed and on PATH)

### Install FFmpeg

**macOS (Homebrew):**
```bash
brew install ffmpeg
```

**Windows:**
1. Download from [gyan.dev/ffmpeg/builds](https://www.gyan.dev/ffmpeg/builds/)
2. Extract and add the `bin/` folder to your system PATH
3. Verify: `ffmpeg -version`

**Linux (Ubuntu/Debian):**
```bash
sudo apt update && sudo apt install ffmpeg
```

---

### Run Locally

```bash
# 1. Clone the repository
git clone https://github.com/yourname/smart-video-cv-optimizer.git
cd smart-video-cv-optimizer

# 2. Create virtual environment
python -m venv .venv

# macOS/Linux:
source .venv/bin/activate

# Windows:
.venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the app
streamlit run app.py
```

The app opens at **http://localhost:8501**

---

## 🐳 Docker

```bash
# Build
docker build -t svcv-optimizer .

# Run
docker run -p 8501:8501 svcv-optimizer
```

---

## ☁️ Cloud Deployment

### Streamlit Cloud (Free)

1. Push your code to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your GitHub repo
4. **Important:** Streamlit Cloud does NOT include FFmpeg by default.  
   Add a `packages.txt` file to your repo:
   ```
   ffmpeg
   ```
5. Deploy — Streamlit will install FFmpeg via `apt`.

### Railway

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login and deploy
railway login
railway init
railway up
```

Railway will auto-detect the `Dockerfile` and deploy accordingly.

### Render

1. Create a new **Web Service** on [render.com](https://render.com)
2. Connect your GitHub repo
3. Set the environment to **Docker**
4. Render will build and deploy from the `Dockerfile`
5. Set port to **8501**

---

## 🗂️ Project Structure

```
smart-video-cv-optimizer/
├── app.py              # Main Streamlit UI
├── analysis.py         # Video metadata extraction (FFprobe)
├── compression.py      # FFmpeg two-pass compression engine
├── utils.py            # Formatting, validation, file helpers
├── requirements.txt    # Python dependencies
├── Dockerfile          # Production Docker image
├── .gitignore
├── .streamlit/
│   └── config.toml     # Streamlit theme + server config
└── README.md
```

---

## ⚙️ Quality Modes Explained

| Mode | CRF | Preset | Best For |
|---|---|---|---|
| **RSSP Optimized** | 21 | medium | Scholarship & university applications |
| **Maximum Quality** | 18 | slow | When quality is paramount |
| **Balanced** | 23 | medium | General-purpose compression |
| **Smallest File** | 28 | fast | Email attachments, strict size limits |

---

## 🎙️ Audio Processing

All modes apply:
- **EBU R128 loudness normalization** (`-16 LUFS`) — broadcast standard
- **High-pass filter at 80 Hz** — removes keyboard/handling noise
- **Low-pass filter at 8 kHz** — preserves speech, removes hiss
- **AAC encoding** at 96–192 kbps depending on mode

---

## 🔧 Technical Details

### Compression Pipeline

1. **Analysis:** FFprobe extracts full metadata
2. **Bitrate calculation:** Target size → optimal video/audio bitrates
3. **Resolution check:** Downscale only if bitrate is too low for current resolution
4. **Two-pass encoding:**
   - Pass 1: Analyse video complexity
   - Pass 2: Encode with precise bitrate allocation
5. **Audio filtering:** Loudness normalization + speech optimization
6. **Cleanup:** Temp files removed automatically

### Supported Inputs

| Format | Extension |
|---|---|
| MP4 | `.mp4` |
| QuickTime | `.mov` |
| AVI | `.avi` |
| Matroska | `.mkv` |

### Output

Always exports as **H.264 + AAC in MP4** — universally compatible.

---

## 🤝 Contributing

Pull requests are welcome. Please open an issue first for major changes.

---

## 📄 License

MIT License — free for personal and commercial use.

---

*Built for RSSP students and scholarship applicants worldwide.*
