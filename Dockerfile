# spotDL GUI Dockerfile
# Pinned to spotdl 4.2.11 — last stable version before the February 2026
# Spotify API changes broke newer releases.
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

# Pin to 4.2.11 — last stable version with --csv support and working
# YouTube Music audio provider
RUN pip install --no-cache-dir \
    "spotdl==4.2.11" \
    flask \
    gunicorn

# Apply patches for Spotify API changes that affect even 4.2.11
RUN python3 - << 'PATCHEOF'
import spotdl.types.song as _s
song_path = _s.__file__

with open(song_path) as f:
    src = f.read()

replacements = [
    (
        'genres=raw_album_meta["genres"] + raw_artist_meta["genres"]',
        'genres=(raw_album_meta.get("genres") or []) + (raw_artist_meta.get("genres") or [])'
    ),
    (
        'publisher=raw_album_meta["label"]',
        'publisher=raw_album_meta.get("label")'
    ),
    (
        'popularity=raw_track_meta["popularity"]',
        'popularity=raw_track_meta.get("popularity")'
    ),
]

patched = 0
for old, new in replacements:
    if old in src:
        src = src.replace(old, new)
        print(f"  ✓ song.py: patched {old[:60]}...")
        patched += 1
    else:
        print(f"  — song.py: already patched or not found: {old[:60]}...")

with open(song_path, 'w') as f:
    f.write(src)

import spotdl.utils.metadata as _m
meta_path = _m.__file__

with open(meta_path) as f:
    src = f.read()

meta_replacements = [
    ('if song.genres:', 'if song.genres and song.genres is not None:'),
    ('if song.publisher:', 'if song.publisher and song.publisher is not None:'),
    ('if song.popularity:', 'if song.popularity and song.popularity is not None:'),
]

for old, new in meta_replacements:
    if old in src:
        src = src.replace(old, new)
        print(f"  ✓ metadata.py: patched {old}")
        patched += 1

with open(meta_path, 'w') as f:
    f.write(src)

print(f"\nAll done — {patched} patches applied.")
PATCHEOF

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
