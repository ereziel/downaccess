"""
Rapport d'erreur DownAccess.
Construit et envoie un rapport JSON au backend PHP via HTTPS.
"""
import importlib.metadata
import json
import platform
import threading
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Callable

from app.version import __version__

REPORT_URL = "https://mathieumartin.ovh/api/downaccess-report"
_BEARER    = "a5b84358b988e5e1fecbf2bc28191bb279db2769bf95c2b0df74b4246dabd93e"

_MAX_VERBOSE  = 100_000   # caractères
_MAX_COMMENT  =   2_000


def build_report(
    url: str,
    site: str,
    format_spec: str,
    error_message: str,
    verbose_log: str,
    user_comment: str,
) -> dict:
    try:
        ytdlp_ver = importlib.metadata.version("yt-dlp")
    except Exception:
        ytdlp_ver = "inconnu"

    return {
        "app_version":   __version__,
        "ytdlp_version": ytdlp_ver,
        "os":            platform.version(),
        "timestamp":     datetime.now(timezone.utc).isoformat(),
        "url":           url or "",
        "site":          site or "",
        "format_spec":   format_spec or "",
        "error_message": error_message or "",
        "verbose_log":   (verbose_log or "")[:_MAX_VERBOSE],
        "user_comment":  (user_comment or "")[:_MAX_COMMENT],
    }


def send_report(report: dict, on_done: Callable[[bool, str], None]) -> None:
    """
    Envoie le rapport en arrière-plan.
    on_done(success, message) est appelé dans le thread — utiliser wx.CallAfter côté UI.
    """
    def _run() -> None:
        try:
            data = json.dumps(report, ensure_ascii=False).encode("utf-8")
            req  = urllib.request.Request(REPORT_URL, data=data, method="POST")
            req.add_header("Content-Type", "application/json; charset=utf-8")
            req.add_header("Authorization", f"Bearer {_BEARER}")
            with urllib.request.urlopen(req, timeout=15) as resp:
                body = json.loads(resp.read())
            if body.get("ok"):
                on_done(True, "Rapport envoyé avec succès.")
            else:
                on_done(False, body.get("message", "Erreur inconnue."))

        except urllib.error.HTTPError as exc:
            try:
                body = json.loads(exc.read())
                on_done(False, body.get("message", f"Erreur HTTP {exc.code}."))
            except Exception:
                on_done(False, f"Erreur HTTP {exc.code}.")
        except Exception as exc:
            on_done(False, str(exc))

    threading.Thread(target=_run, daemon=True).start()
