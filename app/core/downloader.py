import io
import logging
import re
import time
import threading
from dataclasses import dataclass, field
from typing import Callable

import yt_dlp

from app.core.ffmpeg_utils import get_ffmpeg_path

_log = logging.getLogger("downaccess.downloader")


@dataclass
class DownloadInfo:
    download_id: str
    url: str
    title: str = ""
    site: str = ""
    fmt: str = ""
    raw_formats: list = field(default_factory=list)
    is_playlist: bool = False
    playlist_entries: list = field(default_factory=list)


@dataclass
class DownloadProgress:
    download_id: str
    percent: float = 0.0
    speed: str = ""
    size: str = ""
    status: str = "downloading"  # downloading | finished | error


# Types de callbacks
OnInfoCallback      = Callable[[DownloadInfo], None]
OnProgressCallback  = Callable[[DownloadProgress], None]
OnErrorCallback     = Callable[[str, str], None]   # (download_id, message)


class Downloader:
    """
    Wrapper yt-dlp pour extraction d'infos et téléchargement.
    Tout s'exécute dans le thread appelant — c'est QueueManager
    qui gère le threading.
    """

    def __init__(self, settings: dict):
        self._settings = settings

    # ------------------------------------------------------------------
    # Extraction d'infos (sans télécharger)
    # ------------------------------------------------------------------

    def fetch_info(self, download_id: str, url: str) -> DownloadInfo | None:
        """
        Retourne les métadonnées de l'URL sans télécharger.
        Détecte automatiquement les playlists.
        """
        # Première passe légère pour détecter les playlists
        flat_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,
            "skip_download": True,
        }
        if self._settings.get("proxy_http"):
            flat_opts["proxy"] = self._settings["proxy_http"]

        try:
            with yt_dlp.YoutubeDL(flat_opts) as ydl:
                info = ydl.extract_info(url, download=False)
            if not info:
                return None

            # Playlist détectée
            if info.get("_type") == "playlist" or info.get("entries") is not None:
                entries = list(info.get("entries") or [])
                # Filtrer les entrées None (vidéos privées/supprimées)
                entries = [e for e in entries if e]
                return DownloadInfo(
                    download_id=download_id,
                    url=url,
                    title=info.get("title") or "Playlist",
                    site=info.get("extractor_key") or "—",
                    is_playlist=True,
                    playlist_entries=entries,
                )

            # Vidéo unique — deuxième passe pour avoir les formats détaillés
            full_opts = dict(flat_opts)
            full_opts["extract_flat"] = False
            with yt_dlp.YoutubeDL(full_opts) as ydl:
                info = ydl.extract_info(url, download=False)
            if not info:
                return None

            return DownloadInfo(
                download_id=download_id,
                url=url,
                title=info.get("title") or url,
                site=info.get("extractor_key") or info.get("extractor") or "—",
                fmt=_describe_format(info),
                raw_formats=info.get("formats") or [],
            )
        except yt_dlp.utils.DownloadError as exc:
            raise DownloadError(str(exc)) from exc
        except Exception as exc:
            raise DownloadError(str(exc)) from exc

    # ------------------------------------------------------------------
    # Téléchargement
    # ------------------------------------------------------------------

    def download(
        self,
        download_id: str,
        url: str,
        on_progress: OnProgressCallback,
        stop_event: threading.Event,
        pause_event: threading.Event | None = None,
        format_spec: str = "auto",
        format_id: str | None = None,
        referer: str | None = None,
        cookies: str | None = None,
        verbose: bool = False,
        on_verbose_log: Callable[[str], None] | None = None,
        playlist_title: str | None = None,
    ) -> str | None:
        """
        Télécharge l'URL dans le dossier configuré.
        format_spec    : "auto" | "mp4" | "mp3" | "m4a" | "manual"
        format_id      : format_id yt-dlp spécifique (mode manuel uniquement)
        verbose        : active les logs yt-dlp détaillés (mode diagnostic)
        on_verbose_log : appelé avec le log complet en fin de téléchargement
        playlist_title : titre de la playlist parente (pour l'organisation en sous-dossier)
        """
        _log.info("Démarrage téléchargement id=%s url=%s format=%s", download_id, url, format_spec)
        dest = self._settings.get("download_folder", ".")

        by_site     = self._settings.get("organize_by_site", False)
        by_playlist = self._settings.get("organize_by_playlist", False) and playlist_title

        if by_site and by_playlist:
            pl_safe = _sanitize_dirname(playlist_title)
            outtmpl = f"{dest}/%(extractor_key)s/{pl_safe}/%(title)s.%(ext)s"
        elif by_site:
            outtmpl = f"{dest}/%(extractor_key)s/%(title)s.%(ext)s"
        elif by_playlist:
            pl_safe = _sanitize_dirname(playlist_title)
            outtmpl = f"{dest}/{pl_safe}/%(title)s.%(ext)s"
        else:
            outtmpl = f"{dest}/%(title)s.%(ext)s"

        log_buf = io.StringIO() if verbose else None

        opts = {
            "outtmpl":        outtmpl,
            "quiet":          not verbose,
            "no_warnings":    not verbose,
            "verbose":        verbose,
            "progress_hooks": [self._make_hook(download_id, on_progress, stop_event, pause_event)],
        }

        if verbose and log_buf is not None:
            opts["logger"] = _StringLogger(log_buf)

        if self._settings.get("proxy_http"):
            opts["proxy"] = self._settings["proxy_http"]
        if self._settings.get("user_agent"):
            opts["user_agent"] = self._settings["user_agent"]

        # Headers supplémentaires (provenant de l'UGE)
        headers = {}
        if referer:
            headers["Referer"] = referer
        if cookies:
            headers["Cookie"] = cookies
        if headers:
            opts["http_headers"] = headers

        opts["ffmpeg_location"] = get_ffmpeg_path(self._settings)

        # Impersonation navigateur pour contourner Cloudflare / HTTP/2 obligatoire
        opts["extractor_args"] = {"generic": {"impersonate": [""]}}

        _apply_format(opts, format_spec, format_id)
        _apply_subtitles(opts, self._settings)

        # Options yt-dlp supplémentaires (raw)
        for extra in self._settings.get("ytdlp_extra_opts", []):
            if extra.startswith("--"):
                key = extra.lstrip("-").replace("-", "_")
                opts[key] = True

        subtitle_warning: str | None = None

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
        except yt_dlp.utils.DownloadError as exc:
            err_msg = str(exc)
            if log_buf is not None and on_verbose_log is not None:
                on_verbose_log(log_buf.getvalue())
            _log.error("Échec téléchargement id=%s url=%s — %s", download_id, url, err_msg)
            # Sous-titres inaccessibles → réessayer sans sous-titres,
            # mais conserver l'erreur comme warning reportable.
            if "subtitles" in err_msg.lower() and opts.get("writesubtitles"):
                opts_retry = {k: v for k, v in opts.items()
                              if k not in ("writesubtitles", "writeautomaticsub",
                                           "subtitleslangs", "subtitlesformat")}
                if "postprocessors" in opts_retry:
                    opts_retry["postprocessors"] = [
                        pp for pp in opts_retry["postprocessors"]
                        if pp.get("key") != "FFmpegSubtitlesConvertor"
                    ]
                try:
                    with yt_dlp.YoutubeDL(opts_retry) as ydl:
                        ydl.download([url])
                    subtitle_warning = err_msg
                except yt_dlp.utils.DownloadError as exc2:
                    raise DownloadError(str(exc2)) from exc2
                except Exception as exc2:
                    raise DownloadError(str(exc2)) from exc2
            else:
                raise DownloadError(err_msg) from exc
        except Exception as exc:
            if log_buf is not None and on_verbose_log is not None:
                on_verbose_log(log_buf.getvalue())
            _log.error("Erreur inattendue id=%s url=%s — %s", download_id, url, exc)
            raise DownloadError(str(exc)) from exc

        if log_buf is not None and on_verbose_log is not None:
            on_verbose_log(log_buf.getvalue())

        _log.info("Téléchargement terminé id=%s url=%s", download_id, url)
        return subtitle_warning

    # ------------------------------------------------------------------
    # Hook de progression
    # ------------------------------------------------------------------

    def _make_hook(
        self,
        download_id: str,
        on_progress: OnProgressCallback,
        stop_event: threading.Event,
        pause_event: threading.Event | None = None,
    ):
        def hook(d: dict) -> None:
            # Pause : bloquer jusqu'à reprise
            if pause_event:
                while pause_event.is_set():
                    if stop_event.is_set():
                        raise yt_dlp.utils.DownloadError("Annulé par l'utilisateur")
                    time.sleep(0.1)
            if stop_event.is_set():
                raise yt_dlp.utils.DownloadError("Annulé par l'utilisateur")

            status = d.get("status")
            if status == "downloading":
                pct   = d.get("_percent_str", "0%").strip().replace("%", "")
                speed = d.get("_speed_str", "").strip()
                total = d.get("_total_bytes_str") or d.get("_total_bytes_estimate_str") or ""
                try:
                    percent = float(pct)
                except ValueError:
                    percent = 0.0
                on_progress(DownloadProgress(
                    download_id=download_id,
                    percent=percent,
                    speed=speed,
                    size=total,
                    status="downloading",
                ))
            elif status == "finished":
                on_progress(DownloadProgress(
                    download_id=download_id,
                    percent=100.0,
                    status="finished",
                ))
        return hook


# ------------------------------------------------------------------
# Helpers privés
# ------------------------------------------------------------------

def _describe_format(info: dict) -> str:
    ext = info.get("ext") or info.get("format_note") or ""
    height = info.get("height")
    if height:
        return f"{height}p {ext}".strip()
    return ext


def _apply_format(opts: dict, format_spec: str, format_id: str | None = None) -> None:
    """Applique le format yt-dlp et les post-processeurs selon le choix."""
    if format_id:
        # Format manuel spécifique
        opts["format"] = format_id
    elif format_spec == "mp3":
        opts["format"] = "bestaudio/best"
        opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }]
    elif format_spec == "m4a":
        opts["format"] = "bestaudio[ext=m4a]/bestaudio/best"
        opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "m4a",
        }]
    elif format_spec == "mp4":
        opts["format"] = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
        opts["postprocessors"] = [{
            "key": "FFmpegVideoConvertor",
            "preferedformat": "mp4",
        }]
    else:
        # Auto : meilleure qualité disponible
        opts["format"] = "bestvideo+bestaudio/best"


def _apply_subtitles(opts: dict, settings: dict) -> None:
    """Ajoute les options de sous-titres selon les préférences."""
    if not settings.get("auto_subtitles"):
        return
    langs = settings.get("subtitle_langs", ["fr", "en"])
    opts["writesubtitles"]   = True
    opts["writeautomaticsub"] = True
    opts["subtitleslangs"]   = langs
    subfmt = settings.get("subtitle_format", "srt")
    if subfmt != "original":
        opts["subtitlesformat"] = subfmt
        opts.setdefault("postprocessors", []).append({
            "key":    "FFmpegSubtitlesConvertor",
            "format": subfmt,
        })


def _sanitize_dirname(name: str) -> str:
    """Supprime les caractères interdits dans les noms de dossiers Windows."""
    sanitized = re.sub(r'[\\/:*?"<>|]', '_', name)
    return sanitized.strip('. ') or "Playlist"


class DownloadError(Exception):
    pass


class _StringLogger:
    """Logger yt-dlp qui capture toute la sortie dans un StringIO."""

    def __init__(self, buf: io.StringIO) -> None:
        self._buf = buf

    def debug(self, msg: str) -> None:
        self._buf.write(msg + "\n")

    def info(self, msg: str) -> None:
        self._buf.write(msg + "\n")

    def warning(self, msg: str) -> None:
        self._buf.write(f"WARNING: {msg}\n")

    def error(self, msg: str) -> None:
        self._buf.write(f"ERROR: {msg}\n")
