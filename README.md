# spotDL GUI — Enhanced Fork

<p align="center">
  <img src="https://raw.githubusercontent.com/LFFPicard/spotDL-GUI/master/assets/logo.png" width="150" alt="spotDL GUI logo">
</p>

[![License: MIT](https://img.shields.io/github/license/LFFPicard/spotDL-GUI?color=44CC11&style=flat-square)](LICENSE)
[![Docker Image](https://img.shields.io/docker/pulls/lffpicard/spotdl-gui?style=flat-square)](https://hub.docker.com/r/lffpicard/spotdl-gui)
[![GitHub Stars](https://img.shields.io/github/stars/LFFPicard/spotDL-GUI?style=flat-square)](https://github.com/LFFPicard/spotDL-GUI/stargazers)

A fork of [Neuvillette-dc/spotify-downloader](https://github.com/Neuvillette-dc/spotify-downloader) (itself a fork of [spotDL/spotify-downloader](https://github.com/spotDL/spotify-downloader)) with a **Flask web GUI**, **Unraid Community Applications support**, and several bug fixes.

> Download your Spotify playlists, albums, artists and tracks along with embedded album art, synced lyrics and rich metadata — sourced from YouTube.

---

## ✨ What this fork adds

### 🖥️ Web GUI
A clean browser-based interface so you never need to touch the command line:
- Download by Spotify URL — track, album, playlist or artist
- Download via CSV export from [Exportify](https://exportify.net) — **no Spotify API credentials required**
- Output format, bitrate and file template controls
- Real-time log streaming with colour-coded output
- Job queue with cancel support
- Built-in file browser for your music directory
- Settings tab for Spotify API credentials and YouTube cookie file

### 🐳 Unraid Community Applications template
A ready-made template for Unraid users — one-click install from the Apps store. Config and credentials are stored in appdata, completely separate from your music share.

### 🐛 Bug fixes over Neuvillette Edition
- **`KeyError: 'genres'`** — fixed crash when Spotify API returns incomplete genre data for a track or album
- **`--skip-existing` flag removed** — replaced with the correct `--overwrite skip` syntax for this version of spotDL

### Everything from the Neuvillette Edition
- Direct CSV downloading (no Spotify account needed)
- Reliable synced lyrics via `syncedlyrics`
- Robust metadata — no more "Invalid MultiSpec" errors
- Graceful Ctrl+C handling
- Suppressed non-fatal 401 noise from Musixmatch

---

## 🚀 Installation

### Option A — Docker (recommended, any Linux distro)

```bash
docker run -d \
  --name spotDL-GUI \
  --restart unless-stopped \
  -p 5000:5000 \
  -v /path/to/your/music:/music \
  -v /path/to/appdata/spotDL-GUI:/config \
  lffpicard/spotdl-gui:latest
```

Then open `http://localhost:5000` in your browser.

### Option B — Docker Compose

```yaml
version: "3"
services:
  spotdl-gui:
    image: lffpicard/spotdl-gui:latest
    container_name: spotDL-GUI
    restart: unless-stopped
    ports:
      - "5000:5000"
    volumes:
      - /path/to/your/music:/music
      - /path/to/appdata/spotDL-GUI:/config
```

### Option C — Unraid Community Applications

1. Open the **Apps** tab in Unraid
2. Search for **spotDL-GUI**
3. Click **Install** and set your music output path
4. Access the GUI via the WebUI button in the Docker tab

### Option D — Build from source

```bash
git clone https://github.com/LFFPicard/spotDL-GUI.git
cd spotDL-GUI
docker build -t spotdl-gui .
docker run -d -p 5000:5000 -v /path/to/music:/music -v /path/to/config:/config spotdl-gui
```

---

## 📖 Usage

### Downloading via Spotify URL
Paste any Spotify URL into the URL box — one per line if you want multiple at once:

| Type | Example |
|---|---|
| Track | `https://open.spotify.com/track/...` |
| Album | `https://open.spotify.com/album/...` |
| Playlist | `https://open.spotify.com/playlist/...` |
| Artist | `https://open.spotify.com/artist/...` |

> **Note:** URL downloads require your own Spotify Developer API credentials (see below). The artist URL will attempt to download the full discography so be prepared for large jobs.

### Downloading via CSV (no credentials needed)
1. Go to [exportify.net](https://exportify.net) and log in with your Spotify account
2. Export any playlist as a CSV file
3. In the GUI, drag and drop (or click to browse) the CSV file into the upload zone
4. Hit **Start Download**

This mode bypasses the Spotify API entirely — perfect if you don't have developer credentials or hit rate limits.

---

## ⚙️ Configuration

### Spotify API Credentials
Using your own credentials avoids rate-limit errors on large downloads.

1. Go to [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard)
2. Log in with your **Spotify Premium** account
3. Click **Create App**, give it any name, set redirect URI to `http://localhost`
4. Copy the **Client ID** and **Client Secret**
5. Paste them into the **Settings** tab in the GUI and click Save

> **Important:** The Spotify Developer API requires the account owner to have Spotify Premium as of late 2024. The credentials are stored in your `/config` directory (appdata on Unraid), not in your music share.

### YouTube Cookie File
Helps bypass YouTube rate limits and unlocks age-restricted content.

1. Install the [Get cookies.txt Locally](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc) extension (Chrome/Edge) or [cookies.txt](https://addons.mozilla.org/firefox/addon/cookies-txt/) (Firefox)
2. Log into YouTube in your browser
3. Export cookies for **youtube.com**
4. Upload the file in the **Settings** tab in the GUI

---

## 📁 Volume Paths

| Container Path | Purpose | Recommended Host Path (Unraid) |
|---|---|---|
| `/music` | Downloaded music output | `/mnt/user/Music/spotDL` |
| `/config` | App config, credentials, cookie file | `/mnt/user/appdata/spotDL-GUI` |

---

## 🔧 Environment Variables

| Variable | Default | Description |
|---|---|---|
| `PORT` | `5000` | Web GUI port |
| `MUSIC_DIR` | `/music` | Music output path inside container |
| `CONFIG_DIR` | `/config` | Config/credentials path inside container |
| `PUID` | `99` | User ID for file ownership |
| `PGID` | `100` | Group ID for file ownership |

---

## 🙏 Credits

- **Original project:** [spotDL/spotify-downloader](https://github.com/spotDL/spotify-downloader)
- **Neuvillette Edition** (CSV support, lyrics, metadata fixes): [Neuvillette-dc/spotify-downloader](https://github.com/Neuvillette-dc/spotify-downloader)
- **This fork** (Web GUI, Unraid template, bug fixes): [LFFPicard/spotDL-GUI](https://github.com/LFFPicard/spotDL-GUI)

---

## ⚖️ License

MIT — see [LICENSE](LICENSE) for details.
