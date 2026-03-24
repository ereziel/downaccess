import json
import os
from pathlib import Path

DEFAULTS: dict = {
    "download_folder": str(Path.home() / "Downloads"),
    "max_concurrent_downloads": 2,
    "post_processing": "none",      # none | mp4 | mp3 | m4a
    "open_folder_when_done": False,
    "ffmpeg_path": "ffmpeg",
    "proxy_http": "",
    "proxy_socks": "",
    "user_agent": "",
    "auto_subtitles": False,
    "subtitle_langs": ["fr", "en"],
    "subtitle_format": "srt",       # srt | vtt | original
    "organize_by_site": False,
    "organize_by_playlist": False,
    "clipboard_monitor": False,
    "ytdlp_extra_opts": [],
    "user_email": "",
    "use_webview_cookies": False,
}


def _config_dir() -> Path:
    appdata = os.environ.get("APPDATA", str(Path.home()))
    path = Path(appdata) / "DownAccess"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _config_file() -> Path:
    return _config_dir() / "settings.json"


def load() -> dict:
    cfg = dict(DEFAULTS)
    try:
        with open(_config_file(), "r", encoding="utf-8") as f:
            saved = json.load(f)
        cfg.update({k: v for k, v in saved.items() if k in DEFAULTS})
    except FileNotFoundError:
        pass
    return cfg


def save(settings: dict) -> None:
    with open(_config_file(), "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)
