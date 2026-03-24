# spotDL GUI Dockerfile
# Uses the official spotDL package from PyPI with patches for the
# February 2026 Spotify API changes.
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

# Apply patches for February 2026 Spotify API changes.
# Spotify stopped returning 'genres', 'label' and 'popularity' for some
# tracks/albums. This patch makes those fields optional in song.py and
# also patches metadata.py to skip writing None values to ID3 tags.
RUN python3 - << 'PATCHEOF'
import re, sys

# ── Patch 1: song.py — make Spotify fields optional ──────────────────────────
import spotdl.types.song as _s
song_path = _s.__file__

with open(song_path) as f:
    src = f.read()

replacements = [
    # genres
    (
        'genres=raw_album_meta["genres"] + raw_artist_meta["genres"]',
        'genres=(raw_album_meta.get("genres") or []) + (raw_artist_meta.get("genres") or [])'
    ),
    # label / publisher
    (
        'publisher=raw_album_meta["label"]',
        'publisher=raw_album_meta.get("label")'
    ),
    # popularity
    (
        'popularity=raw_track_meta["popularity"]',
        'popularity=raw_track_meta.get("popularity")'
    ),
]

for old, new in replacements:
    if old in src:
        src = src.replace(old, new)
        print(f"song.py ✓ patched: {old[:50]}...")
    else:
        print(f"song.py — already patched or not found: {old[:50]}...")

with open(song_path, 'w') as f:
    f.write(src)

# ── Patch 2: metadata.py — skip None values when embedding tags ───────────────
import spotdl.utils.metadata as _m
meta_path = _m.__file__

with open(meta_path) as f:
    src = f.read()

# Wrap the embed block so that None tag values are skipped rather than
# written — this prevents MetadataError when Spotify returns incomplete data.
old_embed = 'if song.genres:'
new_embed = 'if song.genres and song.genres is not None:'

# Also guard publisher/popularity writes
publisher_old = 'if song.publisher:'
publisher_new = 'if song.publisher and song.publisher is not None:'

popularity_old = 'if song.popularity:'
popularity_new = 'if song.popularity and song.popularity is not None:'

patched = False
for old, new in [(old_embed, new_embed), (publisher_old, publisher_new), (popularity_old, popularity_new)]:
    if old in src:
        src = src.replace(old, new)
        print(f"metadata.py ✓ patched: {old}")
        patched = True

if not patched:
    print("metadata.py — no matching patterns found, may already be patched")

with open(meta_path, 'w') as f:
    f.write(src)

print("All patches complete.")
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
