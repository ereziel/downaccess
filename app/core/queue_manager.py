import logging
import threading
import uuid
from dataclasses import dataclass, field
from typing import Callable

import wx

from app.core.downloader import Downloader, DownloadError, DownloadInfo, DownloadProgress

_log = logging.getLogger("downaccess.queue")


@dataclass
class QueueItem:
    download_id: str
    url: str
    format_spec: str = "auto"        # auto | mp4 | mp3 | m4a | manual
    format_id: str | None = None     # format_id yt-dlp (mode manuel)
    referer: str | None = None       # Referer HTTP (UGE)
    cookies: str | None = None       # Cookies de session (UGE, document.cookie)
    playlist_title: str | None = None   # Titre de la playlist parente (organisation dossier)
    playlist_number: int | None = None # Numéro dans la playlist (1-based)
    use_cookies: bool = False          # Forcer les cookies navigateur (retry)
    stop_event:  threading.Event = field(default_factory=threading.Event)
    pause_event: threading.Event = field(default_factory=threading.Event)


# Callbacks UI (toujours appelés via wx.CallAfter)
OnInfoReady     = Callable[[DownloadInfo], None]
OnProgress      = Callable[[DownloadProgress], None]
OnComplete      = Callable[[str], None]           # download_id
OnError         = Callable[[str, str], None]      # download_id, message
OnPlaylist      = Callable[[DownloadInfo], None]  # info avec is_playlist=True
OnWarning       = Callable[[str, str], None]      # download_id, message


class QueueManager:
    """
    Gère la file de téléchargement.
    - Les téléchargements tournent dans des threads daemon séparés.
    - La communication vers l'UI passe TOUJOURS par wx.CallAfter.
    """

    def __init__(
        self,
        settings: dict,
        on_info:     OnInfoReady,
        on_progress: OnProgress,
        on_complete: OnComplete,
        on_error:    OnError,
        on_playlist: OnPlaylist | None = None,
        on_warning:  OnWarning  | None = None,
    ):
        self._settings    = settings
        self._on_info     = on_info
        self._on_progress = on_progress
        self._on_complete = on_complete
        self._on_error    = on_error
        self._on_playlist = on_playlist
        self._on_warning  = on_warning

        self._queue:   list[QueueItem]        = []
        self._active:  dict[str, QueueItem]   = {}   # download_id → item
        self._lock     = threading.Lock()

    # ------------------------------------------------------------------
    # API publique
    # ------------------------------------------------------------------

    @property
    def max_concurrent(self) -> int:
        return self._settings.get("max_concurrent_downloads", 2)

    def add(self, url: str, format_spec: str = "auto", format_id: str | None = None,
            referer: str | None = None, cookies: str | None = None,
            playlist_title: str | None = None,
            playlist_number: int | None = None,
            use_cookies: bool = False) -> str:
        """Ajoute une URL à la file. Retourne le download_id."""
        dl_id = str(uuid.uuid4())
        item = QueueItem(
            download_id=dl_id,
            url=url,
            format_spec=format_spec,
            format_id=format_id,
            referer=referer,
            cookies=cookies,
            playlist_title=playlist_title,
            playlist_number=playlist_number,
            use_cookies=use_cookies,
        )
        with self._lock:
            self._queue.append(item)
        _log.info("Ajout file id=%s url=%s format=%s", dl_id, url, format_spec)
        self._try_start_next()
        return dl_id

    def cancel(self, download_id: str) -> None:
        """Annule/supprime un téléchargement (en cours ou en attente)."""
        with self._lock:
            # En cours → signal d'arrêt
            if download_id in self._active:
                self._active[download_id].stop_event.set()
                return
            # En attente → retirer de la file
            self._queue = [i for i in self._queue if i.download_id != download_id]

    def pause(self, download_id: str) -> None:
        with self._lock:
            if download_id in self._active:
                self._active[download_id].pause_event.set()

    def resume(self, download_id: str) -> None:
        with self._lock:
            if download_id in self._active:
                self._active[download_id].pause_event.clear()

    def is_paused(self, download_id: str) -> bool:
        with self._lock:
            if download_id in self._active:
                return self._active[download_id].pause_event.is_set()
        return False

    def is_active(self, download_id: str) -> bool:
        """Retourne True si le téléchargement est en cours (actif)."""
        with self._lock:
            return download_id in self._active

    def move_up(self, download_id: str) -> bool:
        """Remonte un item en attente dans la file. Retourne True si déplacé."""
        with self._lock:
            ids = [i.download_id for i in self._queue]
            if download_id not in ids:
                return False
            idx = ids.index(download_id)
            if idx == 0:
                return False
            self._queue[idx], self._queue[idx - 1] = self._queue[idx - 1], self._queue[idx]
            return True

    def move_down(self, download_id: str) -> bool:
        """Descend un item en attente dans la file. Retourne True si déplacé."""
        with self._lock:
            ids = [i.download_id for i in self._queue]
            if download_id not in ids:
                return False
            idx = ids.index(download_id)
            if idx >= len(self._queue) - 1:
                return False
            self._queue[idx], self._queue[idx + 1] = self._queue[idx + 1], self._queue[idx]
            return True

    def cancel_all(self) -> None:
        with self._lock:
            for item in self._active.values():
                item.stop_event.set()
            self._queue.clear()

    def get_state(self) -> dict:
        """Retourne l'état courant de la file (thread-safe)."""
        with self._lock:
            return {
                "pending": [{"id": i.download_id, "url": i.url} for i in self._queue],
                "active":  [{"id": i.download_id, "url": i.url} for i in self._active.values()],
            }

    # ------------------------------------------------------------------
    # Démarrage des workers
    # ------------------------------------------------------------------

    def _try_start_next(self) -> None:
        with self._lock:
            while len(self._active) < self.max_concurrent and self._queue:
                item = self._queue.pop(0)
                self._active[item.download_id] = item
                t = threading.Thread(
                    target=self._worker,
                    args=(item,),
                    daemon=True,
                )
                t.start()

    def _worker(self, item: QueueItem) -> None:
        dl = Downloader(self._settings)
        dl_id = item.download_id
        _log.info("Démarrage worker id=%s url=%s", dl_id, item.url)

        # 1. Extraction des infos
        try:
            info = dl.fetch_info(dl_id, item.url, use_cookies=item.use_cookies)
            if not info:
                self._finish(dl_id)
                return
            if info.is_playlist:
                # Déléguer la gestion de la playlist à l'UI
                _log.info("Playlist détectée id=%s url=%s", dl_id, item.url)
                wx.CallAfter(self._on_playlist or self._on_info, info)
                self._finish(dl_id)
                return
            wx.CallAfter(self._on_info, info)
        except DownloadError as exc:
            _log.error("Erreur fetch_info id=%s — %s", dl_id, exc)
            wx.CallAfter(self._on_error, dl_id, str(exc))
            self._finish(dl_id)
            return

        if item.stop_event.is_set():
            _log.info("Annulé avant téléchargement id=%s", dl_id)
            self._finish(dl_id)
            return

        # 2. Téléchargement
        def on_progress(prog: DownloadProgress) -> None:
            wx.CallAfter(self._on_progress, prog)

        try:
            warning = dl.download(
                dl_id, item.url, on_progress, item.stop_event,
                pause_event=item.pause_event,
                format_spec=item.format_spec,
                format_id=item.format_id,
                referer=item.referer,
                cookies=item.cookies,
                playlist_title=item.playlist_title,
                playlist_number=item.playlist_number,
                use_cookies=item.use_cookies,
            )
            if warning and self._on_warning:
                wx.CallAfter(self._on_warning, dl_id, warning)
            _log.info("Terminé avec succès id=%s url=%s", dl_id, item.url)
            wx.CallAfter(self._on_complete, dl_id)
        except DownloadError as exc:
            if not item.stop_event.is_set():
                _log.error("Échec téléchargement id=%s — %s", dl_id, exc)
                wx.CallAfter(self._on_error, dl_id, str(exc))
            else:
                _log.info("Annulé pendant téléchargement id=%s", dl_id)

        self._finish(dl_id)

    def _finish(self, download_id: str) -> None:
        with self._lock:
            self._active.pop(download_id, None)
        self._try_start_next()
