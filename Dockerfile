# spotDL GUI Dockerfile
# Uses the official spotDL package from PyPI with targeted bug fixes.
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

# Patch song.py to gracefully handle missing Spotify API fields.
# The Spotify API stopped returning 'genres', 'label' and 'popularity'
# for some tracks/albums as of early 2026. These patches use .get() with
# safe defaults so a missing field no longer crashes the download.
RUN SONG_PY=$(python -c "import spotdl.types.song as s; print(s.__file__)") && \
    echo "Patching $SONG_PY..." && \
    # Fix KeyError: 'genres'
    sed -i \
      's/genres=raw_album_meta\["genres"\] + raw_artist_meta\["genres"\]/genres=(raw_album_meta.get("genres") or []) + (raw_artist_meta.get("genres") or [])/' \
      "$SONG_PY" && \
    # Fix KeyError: 'label' (publisher field)
    sed -i \
      's/publisher=raw_album_meta\["label"\]/publisher=raw_album_meta.get("label")/' \
      "$SONG_PY" && \
    # Fix KeyError: 'popularity'
    sed -i \
      's/popularity=raw_track_meta\["popularity"\]/popularity=raw_track_meta.get("popularity")/' \
      "$SONG_PY" && \
    echo "All patches applied successfully to $SONG_PY"

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
