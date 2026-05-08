# ── Smart Video CV Optimizer · Dockerfile ─────────────────────────────────────
# Base image: Python 3.11 slim
FROM python:3.11-slim

# Build-time metadata
LABEL maintainer="Smart Video CV Optimizer"
LABEL description="Professional video compression for scholarship and university application videos"

# Install FFmpeg (includes ffprobe)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd -m -u 1000 appuser

# Set working directory
WORKDIR /app

# Copy and install Python dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Ensure Streamlit config directory exists
RUN mkdir -p .streamlit

# Set ownership
RUN chown -R appuser:appuser /app
USER appuser

# Create temp directory for video processing
RUN mkdir -p /tmp/svcv_temp

# Expose Streamlit's default port
EXPOSE 8501

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Run the application
ENTRYPOINT ["streamlit", "run", "app.py", \
            "--server.port=8501", \
            "--server.address=0.0.0.0", \
            "--server.headless=true", \
            "--server.fileWatcherType=none", \
            "--browser.gatherUsageStats=false"]
