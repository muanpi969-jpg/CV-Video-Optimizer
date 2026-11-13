Smart Video CV Optimizer

A small web app for compressing scholarship, RSSP, and university application videos without wrecking the quality.
The main use case is simple: take a 60–90 second phone video and get it under a strict upload limit like 20 MB while keeping the face, voice, and overall image usable.
Built with Python, Streamlit, and FFmpeg.


What it does
* Compresses videos to a target size
* Supports MP4 and MOV uploads
* Detects resolution, bitrate, FPS, and duration automatically
* Uses two-pass FFmpeg encoding for more accurate file sizes
* Applies basic speech-focused audio cleanup
* Runs locally or in the browser
* Works on macOS, Windows, Linux, and Docker


Why I built it
A lot of scholarship and immigration applications ask for short introduction videos, but the upload limits are tiny. Most free online compressors either destroy the quality or upload your files to random servers.
I wanted something simple:
* drag in a video
* choose a target size
* export a cleaner result that still looks decent
That’s basically the whole idea.


Tech stack
Tool	Purpose
Python	Backend
Streamlit	Web interface
FFmpeg	Video compression
FFprobe	Video analysis
Docker	Deployment

Features
Feature	Notes
Target size compression	Calculates bitrate automatically
Video analysis	Reads duration, resolution, FPS, bitrate
Quality presets	RSSP, Balanced, Max Quality, Smallest File
Audio cleanup	Loudness normalization + speech-focused filtering
Smart scaling	Reduces resolution only when necessary
Local processing	Files stay on your machine unless deployed online

Install FFmpeg
macOS
brew install ffmpeg
Ubuntu / Debian
sudo apt update
sudo apt install ffmpeg
Windows
Download FFmpeg from:
Gyan.dev FFmpeg Builds
Add the bin folder to your system PATH, then check:
ffmpeg -version


Run locally
Use Python 3.10 or newer (Python 3.11 is used by the Docker image).

git clone https://github.com/muanpi969-jpg/CV-Video-Optimizer.git

cd CV-Video-Optimizer

python -m venv .venv

# macOS/Linux
source .venv/bin/activate

# Windows
.venv\Scripts\activate

pip install -r requirements.txt

streamlit run app.py
The app should open at:
http://localhost:8501

The deployed app is at https://muanpi-cv-video-optimizer.streamlit.app/.


Docker
docker build -t svcv-optimizer .

docker run -p 8501:8501 svcv-optimizer


Deploying online
Streamlit Cloud
1. Push the project changes to the GitHub branch connected to your app.
2. Open Streamlit Community Cloud and connect `muanpi969-jpg/CV-Video-Optimizer`.
3. Select the branch to deploy (normally `main`) and set `app.py` as the entry point.
4. In advanced settings, select a supported Python version of 3.10 or newer; Python 3.11 matches the Docker image.
5. Deploy, or reboot the existing app after changing system dependencies or Streamlit configuration.

Keep `requirements.txt`, `packages.txt`, and `.streamlit/config.toml` at the repository root paths shown below. Community Cloud installs Streamlit from `requirements.txt` and FFmpeg (including FFprobe) from `packages.txt`; it does not use the Dockerfile. The committed Streamlit configuration sets the upload limit to 500 MB to match the app. No API keys or secrets are needed.

On a hosted deployment, uploaded videos are processed on the app's server. The 500 MB upload limit does not guarantee that every file will fit the hosting plan's memory, CPU, or temporary storage limits.


Railway
Railway
Railway detects the Dockerfile automatically.


Render
Render
Create a Docker web service and connect the GitHub repository.


Project structure
CV-Video-Optimizer/
├── app.py
├── analysis.py
├── compression.py
├── utils.py
├── requirements.txt
├── Dockerfile
├── packages.txt
├── .gitignore
├── .streamlit/
│   └── config.toml
└── README.md


Compression flow
1. FFprobe reads the video metadata
2. The app calculates a bitrate budget from the target size
3. Resolution is lowered only if needed
4. FFmpeg runs a two-pass encode
5. Audio normalization is applied
6. Temporary files are removed automatically


Supported input formats
* .mp4
* .mov
* .avi
* .mkv
Output is always:
* H.264 video
* AAC audio
* MP4 container


Notes
This project started as a practical tool for application videos, but it turned into a useful media-processing portfolio project too. The hardest part honestly wasn’t the UI. It was getting reliable file-size targeting without making the video look terrible.
Some videos compress surprisingly well. Others fight you the whole way.


License
MIT License. Use it however you want.
