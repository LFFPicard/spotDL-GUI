#!/usr/bin/env python3
"""
spotDL Web GUI — Neuvillette Edition
Flask web interface with Spotify API credentials and YouTube cookie file support.
Config is persisted to /music/.spotdl-gui-config.json inside the container.
"""

import os
import uuid
import json
import queue
import threading
import subprocess
from pathlib import Path
from datetime import datetime
from flask import Flask, Response, render_template_string, request, jsonify

app = Flask(__name__)

MUSIC_DIR   = os.environ.get("MUSIC_DIR", "/music")
CONFIG_DIR  = os.environ.get("CONFIG_DIR", "/config")
SPOTDL_CMD  = os.environ.get("SPOTDL_CMD", "spotdl")
CONFIG_FILE = os.path.join(CONFIG_DIR, "spotdl-gui-config.json")
COOKIE_FILE = os.path.join(CONFIG_DIR, "cookies.txt")

DEFAULT_CONFIG = {
    "spotify_client_id":     "",
    "spotify_client_secret": "",
    "use_cookies":           False,
}

def load_config() -> dict:
    try:
        with open(CONFIG_FILE) as f:
            return {**DEFAULT_CONFIG, **json.load(f)}
    except Exception:
        return dict(DEFAULT_CONFIG)

def save_config(data: dict):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ---------------------------------------------------------------------------
# Job management
# ---------------------------------------------------------------------------
jobs: dict = {}
jobs_lock = threading.Lock()

def run_job(job_id: str, cmd: list, output_dir: str):
    with jobs_lock:
        jobs[job_id]["status"]     = "running"
        jobs[job_id]["started_at"] = datetime.now().isoformat()
    log_q = jobs[job_id]["queue"]
    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            cwd=output_dir, text=True, bufsize=1)
        with jobs_lock:
            jobs[job_id]["pid"] = proc.pid
        for line in proc.stdout:
            log_q.put(("log", line.rstrip("\n")))
        proc.wait()
        status = "done" if proc.returncode == 0 else "error"
        with jobs_lock:
            jobs[job_id]["status"]      = status
            jobs[job_id]["returncode"]  = proc.returncode
            jobs[job_id]["finished_at"] = datetime.now().isoformat()
        log_q.put(("status", status))
    except Exception as e:
        with jobs_lock:
            jobs[job_id]["status"] = "error"
        log_q.put(("log", f"[GUI ERROR] {e}"))
        log_q.put(("status", "error"))
    finally:
        log_q.put(("done", ""))

# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------
HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>spotDL GUI</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;800&family=DM+Mono:wght@400;500&display=swap');
  :root{--bg:#0d0f0e;--surface:#161a18;--card:#1c2220;--border:#2a332f;--green:#1db954;--amber:#f59e0b;--red:#ef4444;--text:#e8ede9;--muted:#7a8c82;--font-head:'Syne',sans-serif;--font-mono:'DM Mono',monospace}
  *,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
  body{background:var(--bg);color:var(--text);font-family:var(--font-head);min-height:100vh;display:flex;flex-direction:column}
  header{display:flex;align-items:center;gap:14px;padding:18px 32px;border-bottom:1px solid var(--border);background:var(--surface);position:sticky;top:0;z-index:100}
  .logo{width:36px;height:36px;background:var(--green);border-radius:50%;display:grid;place-items:center;flex-shrink:0}
  .logo svg{width:20px;height:20px;fill:#000}
  header h1{font-size:1.25rem;font-weight:800;letter-spacing:-.02em}
  header h1 span{color:var(--green)}
  .header-badge{margin-left:auto;font-family:var(--font-mono);font-size:.7rem;color:var(--muted);background:var(--card);border:1px solid var(--border);padding:3px 10px;border-radius:20px}
  .container{display:grid;grid-template-columns:380px 1fr;flex:1;height:calc(100vh - 73px)}
  .sidebar{border-right:1px solid var(--border);overflow-y:auto;padding:24px;display:flex;flex-direction:column;gap:20px;background:var(--surface)}
  .main{display:flex;flex-direction:column;overflow:hidden}
  .tabs{display:flex;border-bottom:1px solid var(--border);background:var(--surface);padding:0 24px}
  .tab-btn{background:none;border:none;cursor:pointer;color:var(--muted);font-family:var(--font-head);font-size:.85rem;font-weight:600;padding:14px 16px;border-bottom:2px solid transparent;transition:all .2s;letter-spacing:.03em;text-transform:uppercase}
  .tab-btn.active{color:var(--green);border-bottom-color:var(--green)}
  .tab-btn:hover:not(.active){color:var(--text)}
  .tab-panel{display:none;flex:1;overflow-y:auto;padding:24px}
  .tab-panel.active{display:block}
  .section-title{font-size:.7rem;font-weight:600;text-transform:uppercase;letter-spacing:.1em;color:var(--muted);margin-bottom:10px}
  label{font-size:.8rem;color:var(--muted);display:block;margin-bottom:5px}
  input[type=text],input[type=url],input[type=password],select,textarea{width:100%;background:var(--card);border:1px solid var(--border);border-radius:8px;padding:10px 14px;color:var(--text);font-family:var(--font-mono);font-size:.82rem;outline:none;transition:border-color .2s}
  input[type=text]:focus,input[type=url]:focus,input[type=password]:focus,select:focus,textarea:focus{border-color:var(--green)}
  select option{background:var(--card)}
  textarea{resize:vertical;min-height:70px}
  .field{margin-bottom:14px}
  .btn{display:inline-flex;align-items:center;gap:7px;padding:10px 20px;border-radius:8px;border:none;font-family:var(--font-head);font-weight:600;font-size:.85rem;cursor:pointer;transition:all .2s;letter-spacing:.02em}
  .btn-primary{background:var(--green);color:#000}
  .btn-primary:hover{background:#22d160;transform:translateY(-1px)}
  .btn-danger{background:var(--red);color:#fff}
  .btn-danger:hover{opacity:.85}
  .btn-ghost{background:var(--card);color:var(--text);border:1px solid var(--border)}
  .btn-ghost:hover{border-color:var(--green);color:var(--green)}
  .btn:disabled{opacity:.4;pointer-events:none}
  .btn-full{width:100%;justify-content:center}
  .toggle-row{display:flex;align-items:center;justify-content:space-between;padding:8px 0}
  .toggle-label{font-size:.82rem}
  .toggle{position:relative;width:40px;height:22px;flex-shrink:0}
  .toggle input{opacity:0;width:0;height:0}
  .slider{position:absolute;inset:0;background:var(--border);border-radius:22px;cursor:pointer;transition:.2s}
  .slider::before{content:'';position:absolute;width:16px;height:16px;left:3px;top:3px;background:#fff;border-radius:50%;transition:.2s}
  .toggle input:checked+.slider{background:var(--green)}
  .toggle input:checked+.slider::before{transform:translateX(18px)}
  .upload-zone{display:block;border:2px dashed var(--border);border-radius:10px;padding:20px;text-align:center;cursor:pointer;transition:all .2s;min-height:90px}
  .upload-zone:hover,.upload-zone.drag{border-color:var(--green);background:rgba(29,185,84,.05)}
  .upload-zone p{font-size:.8rem;color:var(--muted);margin-top:7px}
  .upload-zone .icon{font-size:1.8rem;display:block}
  .upload-filename{font-family:var(--font-mono);font-size:.75rem;color:var(--green);margin-top:5px}
  .job-card{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:14px 16px;margin-bottom:10px;cursor:pointer;transition:border-color .2s}
  .job-card:hover{border-color:var(--green)}
  .job-card.selected{border-color:var(--green)}
  .job-header{display:flex;justify-content:space-between;align-items:flex-start;gap:8px}
  .job-query{font-size:.82rem;font-weight:600;word-break:break-all;flex:1}
  .job-meta{font-family:var(--font-mono);font-size:.7rem;color:var(--muted);margin-top:4px}
  .badge{display:inline-block;padding:2px 8px;border-radius:20px;font-size:.65rem;font-weight:700;letter-spacing:.05em;text-transform:uppercase;flex-shrink:0}
  .badge-running{background:rgba(29,185,84,.15);color:var(--green)}
  .badge-done{background:rgba(29,185,84,.08);color:#5a8f6a}
  .badge-error{background:rgba(239,68,68,.15);color:var(--red)}
  .badge-queued{background:rgba(245,158,11,.15);color:var(--amber)}
  .badge-cancelled{background:rgba(120,120,120,.15);color:var(--muted)}
  .log-header{display:flex;align-items:center;justify-content:space-between;padding:14px 20px;border-bottom:1px solid var(--border);background:var(--surface)}
  .log-title{font-size:.85rem;font-weight:600}
  #log-output{flex:1;overflow-y:auto;padding:16px 20px;font-family:var(--font-mono);font-size:.75rem;line-height:1.7;background:var(--bg);white-space:pre-wrap;word-break:break-all}
  #log-output .log-line{display:block}
  #log-output .log-line.ok{color:var(--green)}
  #log-output .log-line.err{color:var(--red)}
  #log-output .log-line.warn{color:var(--amber)}
  #log-output .log-line.info{color:var(--muted)}
  .log-placeholder{display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;gap:10px;color:var(--muted);font-size:.82rem}
  .log-placeholder .big{font-size:3rem}
  .file-row{display:flex;align-items:center;gap:12px;padding:10px 12px;border-radius:8px;border:1px solid transparent;margin-bottom:4px;transition:all .15s}
  .file-row:hover{background:var(--card);border-color:var(--border)}
  .file-icon{font-size:1.1rem;flex-shrink:0}
  .file-name{font-size:.82rem;flex:1;word-break:break-all}
  .file-size{font-family:var(--font-mono);font-size:.7rem;color:var(--muted);flex-shrink:0}
  .breadcrumb{font-family:var(--font-mono);font-size:.75rem;color:var(--muted);margin-bottom:14px;display:flex;align-items:center;gap:6px;flex-wrap:wrap}
  .breadcrumb a{color:var(--green);text-decoration:none}
  .breadcrumb a:hover{text-decoration:underline}
  /* Settings */
  .settings-group{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:18px;margin-bottom:18px}
  .settings-group .section-title{margin-bottom:14px}
  .settings-hint{font-size:.75rem;color:var(--muted);margin-bottom:14px;line-height:1.6}
  .settings-hint a{color:var(--green);text-decoration:none}
  .settings-hint a:hover{text-decoration:underline}
  .settings-hint code{font-family:var(--font-mono);background:var(--bg);padding:1px 5px;border-radius:3px}
  .status-pill{display:inline-flex;align-items:center;gap:6px;font-size:.72rem;font-family:var(--font-mono);padding:4px 10px;border-radius:20px;margin-top:8px}
  .status-pill.set{background:rgba(29,185,84,.12);color:var(--green)}
  .status-pill.unset{background:rgba(245,158,11,.12);color:var(--amber)}
  .status-dot{width:6px;height:6px;border-radius:50%;background:currentColor;flex-shrink:0}
  .toast{position:fixed;bottom:24px;right:24px;background:var(--card);border:1px solid var(--border);border-radius:10px;padding:12px 18px;font-size:.82rem;z-index:999;display:none}
  .toast.show{display:block}
  .toast.ok{border-color:var(--green);color:var(--green)}
  .toast.err{border-color:var(--red);color:var(--red)}
  @keyframes slideIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
  .toast.show{animation:slideIn .2s ease}
  .divider{border:none;border-top:1px solid var(--border);margin:4px 0}
  .empty{text-align:center;color:var(--muted);font-size:.82rem;padding:32px 0}
  @keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
  .pulsing{animation:pulse 1.4s ease-in-out infinite}
  ::-webkit-scrollbar{width:6px}
  ::-webkit-scrollbar-track{background:var(--bg)}
  ::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px}
  ::-webkit-scrollbar-thumb:hover{background:var(--muted)}
  @media(max-width:768px){.container{grid-template-columns:1fr}.sidebar{border-right:none;border-bottom:1px solid var(--border)}}
</style>
</head>
<body>

<header>
  <div class="logo">
    <svg viewBox="0 0 24 24"><path d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z"/></svg>
  </div>
  <h1>spot<span>DL</span> GUI</h1>
  <div class="header-badge">Neuvillette Edition</div>
</header>

<div class="container">
  <aside class="sidebar">
    <section>
      <div class="section-title">Download by URL</div>
      <div class="field">
        <label>Spotify URL(s) — one per line (track / album / playlist / artist)</label>
        <textarea id="urls" rows="4" placeholder="https://open.spotify.com/playlist/...&#10;https://open.spotify.com/album/...&#10;https://open.spotify.com/artist/...&#10;https://open.spotify.com/track/..."></textarea>
      </div>
    </section>

    <div style="display:flex;align-items:center;gap:10px">
      <hr class="divider" style="flex:1"><span style="font-size:.72rem;color:var(--muted);font-weight:600;letter-spacing:.08em">OR</span><hr class="divider" style="flex:1">
    </div>

    <section>
      <div class="section-title">Download via CSV (Exportify)</div>
      <label class="upload-zone" id="csv-zone" for="csv-file">
        <div class="icon">📄</div>
        <p>Click or drag &amp; drop a CSV from exportify.net</p>
        <div class="upload-filename" id="csv-name"></div>
      </label>
      <input type="file" id="csv-file" accept=".csv" style="display:none">
    </section>

    <hr class="divider">

    <section>
      <div class="section-title">Options</div>
      <div class="field">
        <label>Output Format</label>
        <select id="format">
          <option value="mp3">MP3</option><option value="flac">FLAC</option>
          <option value="opus">Opus</option><option value="m4a">M4A</option>
          <option value="wav">WAV</option><option value="ogg">OGG</option>
        </select>
      </div>
      <div class="field">
        <label>Bitrate (MP3 / lossy)</label>
        <select id="bitrate">
          <option value="">Auto</option><option value="320k">320 kbps</option>
          <option value="256k">256 kbps</option><option value="192k">192 kbps</option>
          <option value="128k">128 kbps</option>
        </select>
      </div>
      <div class="field">
        <label>Output Template</label>
        <input type="text" id="output-tmpl" value="{artist}/{album}/{title}.{output-ext}">
      </div>
      <div class="toggle-row">
        <span class="toggle-label">Synced Lyrics (LRC)</span>
        <label class="toggle"><input type="checkbox" id="opt-lyrics" checked><span class="slider"></span></label>
      </div>
      <div class="toggle-row">
        <span class="toggle-label">Skip Existing Files</span>
        <label class="toggle"><input type="checkbox" id="opt-skip" checked><span class="slider"></span></label>
      </div>
      <div class="toggle-row">
        <span class="toggle-label">Overwrite Existing</span>
        <label class="toggle"><input type="checkbox" id="opt-overwrite"><span class="slider"></span></label>
      </div>
    </section>

    <button class="btn btn-primary btn-full" id="dl-btn" onclick="startDownload()">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M12 16l-6-6h4V4h4v6h4z"/><path d="M20 18H4v2h16z"/></svg>
      Start Download
    </button>
  </aside>

  <div class="main">
    <nav class="tabs">
      <button class="tab-btn active" onclick="switchTab('jobs',this)">Jobs</button>
      <button class="tab-btn"        onclick="switchTab('log',this)">Live Log</button>
      <button class="tab-btn"        onclick="switchTab('files',this)">Files</button>
      <button class="tab-btn"        onclick="switchTab('settings',this)">⚙ Settings</button>
    </nav>

    <!-- Jobs -->
    <div class="tab-panel active" id="tab-jobs">
      <div id="jobs-list"><div class="empty">No jobs yet — start a download!</div></div>
    </div>

    <!-- Log -->
    <div class="tab-panel" id="tab-log" style="display:flex;flex-direction:column;padding:0;height:100%">
      <div class="log-header">
        <span class="log-title" id="log-title">No job selected</span>
        <div style="display:flex;gap:8px">
          <button class="btn btn-ghost" style="padding:6px 12px;font-size:.75rem" onclick="clearLog()">Clear</button>
          <button class="btn btn-ghost" style="padding:6px 12px;font-size:.75rem" id="as-btn" onclick="toggleAS()">⬇ Auto-scroll ON</button>
          <button class="btn btn-danger" style="padding:6px 12px;font-size:.75rem" id="cancel-btn" onclick="cancelJob()" disabled>Cancel</button>
        </div>
      </div>
      <div id="log-output">
        <div class="log-placeholder"><div class="big">🎵</div><span>Select a job to view its log.</span></div>
      </div>
    </div>

    <!-- Files -->
    <div class="tab-panel" id="tab-files">
      <div class="breadcrumb" id="breadcrumb"></div>
      <div id="file-list"><div class="empty">Loading…</div></div>
      <div style="margin-top:16px"><button class="btn btn-ghost" onclick="loadFiles()">⟳ Refresh</button></div>
    </div>

    <!-- Settings -->
    <div class="tab-panel" id="tab-settings">

      <div class="settings-group">
        <div class="section-title">🎵 Spotify API Credentials</div>
        <p class="settings-hint">
          Using your own credentials prevents rate-limit errors on large downloads.
          Get them free at <a href="https://developer.spotify.com/dashboard" target="_blank">developer.spotify.com/dashboard</a> —
          create any app and set the redirect URI to <code>http://localhost</code>.
          Copy the Client ID and Client Secret from the app dashboard.
        </p>
        <div class="field">
          <label>Client ID</label>
          <input type="text" id="s-client-id" placeholder="32-character hex string" autocomplete="off">
        </div>
        <div class="field">
          <label>Client Secret</label>
          <input type="password" id="s-client-secret" placeholder="Leave blank to keep existing value" autocomplete="new-password">
        </div>
        <span id="spotify-status" class="status-pill unset"><span class="status-dot"></span>Not configured</span>
      </div>

      <div class="settings-group">
        <div class="section-title">🍪 YouTube / YTM Cookie File</div>
        <p class="settings-hint">
          A cookie file from a logged-in YouTube session helps bypass rate limits and
          unlocks age-restricted content. Export it using the
          <a href="https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc" target="_blank">Get cookies.txt Locally</a>
          extension (Chrome/Edge) or
          <a href="https://addons.mozilla.org/firefox/addon/cookies-txt/" target="_blank">cookies.txt</a> (Firefox).
          Make sure you export cookies for <strong>youtube.com</strong> while logged in.
        </p>
        <label class="upload-zone" id="cookie-zone" for="cookie-input">
          <div class="icon">🍪</div>
          <p>Click or drag &amp; drop your cookies.txt file</p>
          <div class="upload-filename" id="cookie-name"></div>
        </label>
        <input type="file" id="cookie-input" accept=".txt" style="display:none">
        <span id="cookie-status" class="status-pill unset" style="margin-top:10px"><span class="status-dot"></span>No cookie file saved</span>
        <div class="toggle-row" style="margin-top:14px">
          <span class="toggle-label">Use cookie file for all downloads</span>
          <label class="toggle"><input type="checkbox" id="use-cookies"><span class="slider"></span></label>
        </div>
      </div>

      <div style="display:flex;gap:10px">
        <button class="btn btn-primary" onclick="saveSettings()">💾 Save Settings</button>
        <button class="btn btn-ghost"   onclick="loadSettings()">↺ Reload</button>
      </div>

    </div>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
let activeJobId = null, eventSource = null, autoscroll = true;
let currentPath = '', csvFile = null, cookieFile = null;
let toastTimer  = null;

// ── Tabs ──────────────────────────────────────────────────────────────────────
function switchTab(name, btn) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-panel').forEach(p => { p.classList.remove('active'); p.style.display='none'; });
  btn.classList.add('active');
  const p = document.getElementById('tab-'+name);
  p.classList.add('active');
  p.style.display = name === 'log' ? 'flex' : 'block';
  if (name === 'files')    loadFiles(currentPath);
  if (name === 'settings') loadSettings();
}

// ── Toast ─────────────────────────────────────────────────────────────────────
function toast(msg, type='ok') {
  const t = document.getElementById('toast');
  t.textContent = msg; t.className = 'toast show '+type;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.className='toast', 3200);
}

// ── CSV drag/drop ─────────────────────────────────────────────────────────────
document.getElementById('csv-file').addEventListener('change', e => {
  csvFile = e.target.files[0];
  document.getElementById('csv-name').textContent = csvFile ? csvFile.name : '';
});
setupDrop('csv-zone', f => f.name.endsWith('.csv'), f => { csvFile=f; document.getElementById('csv-name').textContent=f.name; });

// ── Cookie drag/drop ──────────────────────────────────────────────────────────
document.getElementById('cookie-input').addEventListener('change', e => {
  cookieFile = e.target.files[0];
  document.getElementById('cookie-name').textContent = cookieFile ? cookieFile.name : '';
});
setupDrop('cookie-zone', () => true, f => { cookieFile=f; document.getElementById('cookie-name').textContent=f.name; });

function setupDrop(id, check, cb) {
  const z = document.getElementById(id);
  z.addEventListener('dragover',  e => { e.preventDefault(); z.classList.add('drag'); });
  z.addEventListener('dragleave', () => z.classList.remove('drag'));
  z.addEventListener('drop', e => {
    e.preventDefault(); z.classList.remove('drag');
    const f = e.dataTransfer.files[0];
    if (f && check(f)) cb(f);
  });
}

// ── Settings ──────────────────────────────────────────────────────────────────
async function loadSettings() {
  const cfg = await fetch('/api/config').then(r => r.json());
  document.getElementById('s-client-id').value   = cfg.spotify_client_id || '';
  document.getElementById('s-client-secret').value = '';           // never echoed back
  document.getElementById('use-cookies').checked = !!cfg.use_cookies;

  const spSet = !!(cfg.spotify_client_id && cfg.spotify_client_secret_set);
  const sp = document.getElementById('spotify-status');
  sp.className = 'status-pill ' + (spSet ? 'set' : 'unset');
  sp.innerHTML = `<span class="status-dot"></span>${spSet ? 'Credentials saved ✓' : 'Not configured — downloads may hit rate limits'}`;

  const ck = document.getElementById('cookie-status');
  ck.className = 'status-pill ' + (cfg.cookie_file_exists ? 'set' : 'unset');
  ck.innerHTML = `<span class="status-dot"></span>${cfg.cookie_file_exists ? 'Cookie file saved ✓' : 'No cookie file saved'}`;
}

async function saveSettings() {
  const fd = new FormData();
  fd.append('spotify_client_id',     document.getElementById('s-client-id').value.trim());
  fd.append('spotify_client_secret', document.getElementById('s-client-secret').value.trim());
  fd.append('use_cookies',           document.getElementById('use-cookies').checked ? '1' : '0');
  if (cookieFile) fd.append('cookie_file', cookieFile);

  const res = await fetch('/api/config', { method:'POST', body:fd });
  const d   = await res.json();
  if (d.ok) {
    toast('Settings saved ✓', 'ok');
    cookieFile = null;
    document.getElementById('cookie-name').textContent = '';
    document.getElementById('cookie-input').value = '';
    loadSettings();
  } else {
    toast('Save failed: ' + (d.error || 'unknown'), 'err');
  }
}

// ── Start download ────────────────────────────────────────────────────────────
async function startDownload() {
  const urlsRaw = document.getElementById('urls').value.trim();
  if (!urlsRaw && !csvFile) { alert('Enter a Spotify URL or upload a CSV.'); return; }

  const fd = new FormData();
  if (urlsRaw) urlsRaw.split('\n').filter(u=>u.trim()).forEach(u => fd.append('urls', u.trim()));
  if (csvFile)  fd.append('csv', csvFile);
  fd.append('format',    document.getElementById('format').value);
  const br = document.getElementById('bitrate').value;
  if (br) fd.append('bitrate', br);
  fd.append('output',   document.getElementById('output-tmpl').value.trim());
  fd.append('lyrics',   document.getElementById('opt-lyrics').checked   ? '1':'0');
  fd.append('skip',     document.getElementById('opt-skip').checked     ? '1':'0');
  fd.append('overwrite',document.getElementById('opt-overwrite').checked? '1':'0');

  const btn = document.getElementById('dl-btn');
  btn.disabled = true; btn.textContent = 'Queuing…';
  try {
    const d = await fetch('/api/download', { method:'POST', body:fd }).then(r=>r.json());
    if (d.job_id) {
      selectJob(d.job_id);
      switchTab('log', document.querySelectorAll('.tab-btn')[1]);
      pollJobs();
    } else { alert('Error: ' + (d.error||'unknown')); }
  } catch(e) { alert('Request failed: '+e); }
  finally {
    btn.disabled = false;
    btn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M12 16l-6-6h4V4h4v6h4z"/><path d="M20 18H4v2h16z"/></svg> Start Download';
  }
}

// ── Jobs ──────────────────────────────────────────────────────────────────────
let pollTimer = null;
async function pollJobs() {
  clearTimeout(pollTimer);
  try {
    const jobs = await fetch('/api/jobs').then(r=>r.json());
    renderJobs(jobs);
    const busy = jobs.some(j=>j.status==='running'||j.status==='queued');
    pollTimer = setTimeout(pollJobs, busy ? 1500 : 5000);
  } catch { pollTimer = setTimeout(pollJobs, 5000); }
}

function renderJobs(jobs) {
  const c = document.getElementById('jobs-list');
  if (!jobs.length) { c.innerHTML='<div class="empty">No jobs yet — start a download!</div>'; return; }
  jobs.sort((a,b)=>b.created_at.localeCompare(a.created_at));
  c.innerHTML = jobs.map(j=>`
    <div class="job-card ${j.id===activeJobId?'selected':''}" onclick="selectJob('${j.id}')">
      <div class="job-header">
        <div class="job-query">${esc(j.query)}</div>
        <span class="badge badge-${j.status} ${j.status==='running'?'pulsing':''}">${j.status}</span>
      </div>
      <div class="job-meta">${j.format.toUpperCase()} · ${j.created_at.substring(0,19).replace('T',' ')}${j.finished_at?' → '+j.finished_at.substring(11,19):''}</div>
    </div>`).join('');
}

// ── Log streaming ─────────────────────────────────────────────────────────────
function selectJob(id) {
  activeJobId = id;
  if (eventSource) { eventSource.close(); eventSource=null; }
  document.querySelectorAll('.job-card').forEach(c=>c.classList.remove('selected'));
  const card = document.querySelector(`.job-card[onclick*="${id}"]`);
  if (card) card.classList.add('selected');
  document.getElementById('log-output').innerHTML = '';
  document.getElementById('cancel-btn').disabled = false;

  eventSource = new EventSource('/api/stream/'+id);
  eventSource.onmessage = e => {
    const {type, data} = JSON.parse(e.data);
    if (type==='log')    appendLog(data);
    if (type==='status') {
      document.getElementById('log-title').textContent = 'Job '+id.substring(0,8)+'… — '+data.toUpperCase();
      if (['done','error','cancelled'].includes(data)) { document.getElementById('cancel-btn').disabled=true; eventSource.close(); pollJobs(); }
    }
    if (type==='done') eventSource.close();
  };
  eventSource.onerror = ()=>eventSource.close();

  fetch('/api/jobs').then(r=>r.json()).then(jobs=>{
    const j=jobs.find(x=>x.id===id);
    if (j) {
      document.getElementById('log-title').textContent = esc(j.query)+' — '+j.status.toUpperCase();
      document.getElementById('cancel-btn').disabled = j.status!=='running';
    }
  });
  switchTab('log', document.querySelectorAll('.tab-btn')[1]);
}

function appendLog(line) {
  const lo = document.getElementById('log-output');
  const ph = lo.querySelector('.log-placeholder'); if (ph) ph.remove();
  const s  = document.createElement('span');
  s.className = 'log-line';
  const l = line.toLowerCase();
  if      (l.includes('error')||l.includes('failed')||l.includes('traceback')) s.classList.add('err');
  else if (l.includes('warning')||l.includes('warn'))  s.classList.add('warn');
  else if (l.includes('downloaded')||l.includes('✓')||l.includes('complete'))  s.classList.add('ok');
  else if (l.startsWith('[')||l.includes('info'))       s.classList.add('info');
  s.textContent = line+'\n'; lo.appendChild(s);
  if (autoscroll) lo.scrollTop = lo.scrollHeight;
}

function clearLog()  { document.getElementById('log-output').innerHTML=''; }
function toggleAS()  { autoscroll=!autoscroll; document.getElementById('as-btn').textContent=autoscroll?'⬇ Auto-scroll ON':'⬇ Auto-scroll OFF'; }
async function cancelJob() {
  if (!activeJobId) return;
  await fetch('/api/cancel/'+activeJobId, {method:'POST'});
  document.getElementById('cancel-btn').disabled=true; pollJobs();
}

// ── Files ─────────────────────────────────────────────────────────────────────
async function loadFiles(sub) {
  currentPath = sub||'';
  const data  = await fetch('/api/files?path='+encodeURIComponent(currentPath)).then(r=>r.json());
  const parts = currentPath ? currentPath.split('/').filter(Boolean) : [];
  document.getElementById('breadcrumb').innerHTML =
    '<a href="#" onclick="loadFiles(\'\');return false;">📁 /music</a>' +
    parts.map((p,i)=>{const s=parts.slice(0,i+1).join('/'); return ` / <a href="#" onclick="loadFiles('${s}');return false;">${esc(p)}</a>`;}).join('');
  const fl = document.getElementById('file-list');
  if (!data.entries||!data.entries.length) { fl.innerHTML='<div class="empty">Empty directory.</div>'; return; }
  fl.innerHTML = data.entries.map(e=>{
    const icon = e.is_dir?'📁':({mp3:'🎵',flac:'🎼',m4a:'🎵',opus:'🎵',wav:'🎤',ogg:'🎵',lrc:'📝',jpg:'🖼',jpeg:'🖼',png:'🖼'}[e.name.split('.').pop().toLowerCase()]||'📄');
    const click = e.is_dir?`onclick="loadFiles('${esc(e.path)}');return false;"` : '';
    return `<div class="file-row" ${click}><span class="file-icon">${icon}</span><span class="file-name">${esc(e.name)}</span><span class="file-size">${e.size}</span></div>`;
  }).join('');
}

function esc(s) { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

pollJobs(); loadFiles();
</script>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/api/config", methods=["GET"])
def api_config_get():
    cfg = load_config()
    # Indicate whether secret is set without sending it back
    cfg["spotify_client_secret_set"] = bool(cfg.get("spotify_client_secret"))
    cfg["spotify_client_secret"]     = ""          # never echo to browser
    cfg["cookie_file_exists"]        = os.path.exists(COOKIE_FILE)
    return jsonify(cfg)


@app.route("/api/config", methods=["POST"])
def api_config_post():
    try:
        cfg           = load_config()
        client_id     = request.form.get("spotify_client_id",     "").strip()
        client_secret = request.form.get("spotify_client_secret", "").strip()
        use_cookies   = request.form.get("use_cookies", "0") == "1"

        if client_id:
            cfg["spotify_client_id"]     = client_id
        if client_secret:
            cfg["spotify_client_secret"] = client_secret
        cfg["use_cookies"] = use_cookies

        cookie_upload = request.files.get("cookie_file")
        if cookie_upload and cookie_upload.filename:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            cookie_upload.save(COOKIE_FILE)

        save_config(cfg)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/download", methods=["POST"])
def api_download():
    urls        = request.form.getlist("urls")
    fmt         = request.form.get("format",   "mp3")
    bitrate     = request.form.get("bitrate",  "")
    output_tmpl = request.form.get("output",   "{artist}/{album}/{title}.{output-ext}")
    lyrics      = request.form.get("lyrics",   "1") == "1"
    skip        = request.form.get("skip",     "1") == "1"
    overwrite   = request.form.get("overwrite","0") == "1"
    csv_file    = request.files.get("csv")
    csv_path    = None

    if not urls and not csv_file:
        return jsonify({"error": "No URLs or CSV provided"}), 400

    job_id = str(uuid.uuid4())
    os.makedirs(MUSIC_DIR, exist_ok=True)

    if csv_file:
        csv_path = os.path.join("/tmp", f"{job_id}.csv")
        csv_file.save(csv_path)

    cfg = load_config()
    cmd = [SPOTDL_CMD, "download"]

    if csv_path:
        cmd += ["--csv", csv_path]
        query = f"CSV: {csv_file.filename}"
    else:
        cmd += urls
        query = urls[0] if len(urls) == 1 else f"{len(urls)} URLs"

    cmd += ["--format", fmt, "--output", output_tmpl]

    if bitrate:
        cmd += ["--bitrate", bitrate]

    if lyrics:
        cmd += ["--lyrics", "synced", "musixmatch", "genius", "azlyrics"]

    if overwrite:
        cmd += ["--overwrite", "force"]
    elif skip:
        cmd += ["--overwrite", "skip"]

    # Inject saved Spotify credentials
    if cfg.get("spotify_client_id"):
        cmd += ["--client-id", cfg["spotify_client_id"]]
    if cfg.get("spotify_client_secret"):
        cmd += ["--client-secret", cfg["spotify_client_secret"]]

    # Inject cookie file if enabled and present
    if cfg.get("use_cookies") and os.path.exists(COOKIE_FILE):
        cmd += ["--cookie-file", COOKIE_FILE]

    job = {
        "id":          job_id,
        "query":       query,
        "format":      fmt,
        "status":      "queued",
        "cmd":         cmd,
        "pid":         None,
        "created_at":  datetime.now().isoformat(),
        "started_at":  None,
        "finished_at": None,
        "returncode":  None,
        "queue":       queue.Queue(),
    }
    with jobs_lock:
        jobs[job_id] = job

    threading.Thread(target=run_job, args=(job_id, cmd, MUSIC_DIR), daemon=True).start()
    return jsonify({"job_id": job_id, "query": query})


@app.route("/api/stream/<job_id>")
def api_stream(job_id: str):
    with jobs_lock:
        job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    log_q    = job["queue"]
    buffered = []
    try:
        while True:
            buffered.append(log_q.get_nowait())
    except queue.Empty:
        pass

    def generate():
        for msg_type, data in buffered:
            yield f"data: {json.dumps({'type': msg_type, 'data': data})}\n\n"
            if msg_type == "done":
                return
        while True:
            try:
                msg_type, data = log_q.get(timeout=30)
                yield f"data: {json.dumps({'type': msg_type, 'data': data})}\n\n"
                if msg_type == "done":
                    return
            except queue.Empty:
                yield 'data: {"type":"ping","data":""}\n\n'

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/api/jobs")
def api_jobs():
    with jobs_lock:
        return jsonify([{
            "id": j["id"], "query": j["query"], "format": j["format"],
            "status": j["status"], "created_at": j["created_at"],
            "started_at": j["started_at"], "finished_at": j["finished_at"],
            "returncode": j["returncode"],
        } for j in jobs.values()])


@app.route("/api/cancel/<job_id>", methods=["POST"])
def api_cancel(job_id: str):
    with jobs_lock:
        job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Not found"}), 404
    pid = job.get("pid")
    if pid:
        try:
            import signal
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    with jobs_lock:
        jobs[job_id]["status"] = "cancelled"
    return jsonify({"ok": True})


@app.route("/api/files")
def api_files():
    rel    = request.args.get("path", "")
    safe   = rel.lstrip("/").replace("..", "")
    target = (Path(MUSIC_DIR) / safe).resolve()
    if not str(target).startswith(str(Path(MUSIC_DIR).resolve())):
        return jsonify({"error": "Forbidden"}), 403
    if not target.exists():
        return jsonify({"entries": []})
    entries = []
    for item in sorted(target.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
        if item.name.startswith("."):
            continue
        size = ""
        if item.is_file():
            b = item.stat().st_size
            size = f"{b/1024/1024:.1f} MB" if b > 1048576 else f"{b/1024:.0f} KB"
        entries.append({"name": item.name, "path": str(item.relative_to(MUSIC_DIR)),
                        "is_dir": item.is_dir(), "size": size})
    return jsonify({"entries": entries, "path": safe})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
