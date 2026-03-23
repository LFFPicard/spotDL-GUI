# spotDL GUI Dockerfile
# Uses the official spotDL package from PyPI — stable and actively maintained.
# https://github.com/LFFPicard/spotDL-GUI

FROM python:3.11-slim

LABEL maintainer="LFFPicard"
LABEL description="spotDL with Web GUI — Unraid ready, CSV support, synced lyrics"
LABEL org.opencontainers.image.source="https://github.com/LFFPicard/spotDL-GUI"

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    aria2 \
    gcc \
    g++ \
    libffi-dev \
    ca-certificates \
    curl \
  && rm -rf /var/lib/apt/lists/*

# Install spotDL from PyPI and Flask/Gunicorn for the web GUI
RUN pip install --no-cache-dir \
    spotdl \
    flask \
    gunicorn

# Copy the web GUI
WORKDIR /app
COPY app.py .

# Volumes
VOLUME /music
VOLUME /config

# Environment
ENV MUSIC_DIR=/music
ENV CONFIG_DIR=/config
ENV PORT=5000
ENV SPOTDL_CMD=spotdl

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "8", "--timeout", "0", "app:app"]
