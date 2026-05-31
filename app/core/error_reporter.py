"""
Rapport d'erreur DownAccess.
Construit et envoie un rapport multipart/form-data au backend PHP via HTTPS.
"""
import importlib.metadata
import io
import json
import platform
import threading
import urllib.error
import urllib.request
import uuid
from datetime import datetime, UTC
from pathlib import Path
from collections.abc import Callable

from app.version import __version__
from app.core.i18n import _translate as _

REPORT_URL  = "https://mathieumartin.ovh/api/downaccess-report"
CONTACT_URL = "https://mathieumartin.ovh/api/downaccess-contact"
_BEARER     = "a5b84358b988e5e1fecbf2bc28191bb279db2769bf95c2b0df74b4246dabd93e"

_MAX_VERBOSE  = 100_000   # caractères
_MAX_COMMENT  =   2_000


def build_report(
    url: str,
    site: str,
    format_spec: str,
    error_message: str,
    verbose_log: str,
    user_comment: str,
    email: str = "",
    preferences: dict | None = None,
    queue_state: dict | None = None,
    system_info: dict | None = None,
) -> dict:
    try:
        ytdlp_ver = importlib.metadata.version("yt-dlp")
    except Exception:
        ytdlp_ver = "inconnu"

    return {
        "app_version":   __version__,
        "ytdlp_version": ytdlp_ver,
        "os":            platform.version(),
        "timestamp":     datetime.now(UTC).isoformat(),
        "url":           url or "",
        "site":          site or "",
        "format_spec":   format_spec or "",
        "error_message": error_message or "",
        "verbose_log":   (verbose_log or "")[:_MAX_VERBOSE],
        "user_comment":  (user_comment or "")[:_MAX_COMMENT],
        "email":         (email or "")[:200],
        "preferences":   preferences or {},
        "queue_state":   queue_state or {},
        "system_info":   system_info or {},
    }


def _make_multipart(fields: dict, files: dict) -> tuple[bytes, str]:
    """Construit un corps multipart/form-data et retourne (body, content_type)."""
    boundary = uuid.uuid4().hex
    body = io.BytesIO()

    for name, value in fields.items():
        body.write(f"--{boundary}\r\n".encode())
        body.write(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        body.write(f"{value}\r\n".encode())

    for name, (filename, content) in files.items():
        body.write(f"--{boundary}\r\n".encode())
        body.write(
            f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
            f"Content-Type: text/plain; charset=utf-8\r\n\r\n"
            .encode()
        )
        body.write(content if isinstance(content, bytes) else content.encode("utf-8"))
        body.write(b"\r\n")

    body.write(f"--{boundary}--\r\n".encode())
    return body.getvalue(), f"multipart/form-data; boundary={boundary}"


def _read_log_file() -> str:
    """Lit le fichier log si disponible, retourne une chaîne vide sinon."""
    try:
        from app.core.logger import get_log_path
        log_path: Path = get_log_path()
        if log_path.exists():
            return log_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        pass
    return ""


def send_report(report: dict, on_done: Callable[[bool, str], None]) -> None:
    """
    Envoie le rapport en multipart/form-data en arrière-plan.
    on_done(success, message) est appelé dans le thread — utiliser wx.CallAfter côté UI.
    """
    def _run() -> None:
        try:
            log_content = _read_log_file()
            fields = {"report": json.dumps(report, ensure_ascii=False)}
            files  = {"log_file": ("downaccess.log", log_content)}
            data, content_type = _make_multipart(fields, files)

            req = urllib.request.Request(REPORT_URL, data=data, method="POST")
            req.add_header("Content-Type", content_type)
            req.add_header("Authorization", f"Bearer {_BEARER}")
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = json.loads(resp.read())
            if body.get("ok"):
                on_done(True, _("Rapport envoyé avec succès."))
            else:
                on_done(False, body.get("message", _("Erreur inconnue.")))

        except urllib.error.HTTPError as exc:
            try:
                body = json.loads(exc.read())
                on_done(False, body.get("message", _("Erreur HTTP {code}.").format(code=exc.code)))
            except Exception:
                on_done(False, _("Erreur HTTP {code}.").format(code=exc.code))
        except Exception as exc:
            on_done(False, str(exc))

    threading.Thread(target=_run, daemon=True).start()


def send_contact(
    contact_type: str,
    email: str,
    message: str,
    on_done: Callable[[bool, str], None],
) -> None:
    """
    Envoie un message de contact/suggestion en arrière-plan.
    on_done(success, message) est appelé dans le thread — utiliser wx.CallAfter côté UI.
    """
    payload = {
        "app_version": __version__,
        "contact_type": contact_type,
        "email": email,
        "message": message[:2000],
    }

    def _run() -> None:
        try:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            req  = urllib.request.Request(CONTACT_URL, data=data, method="POST")
            req.add_header("Content-Type", "application/json; charset=utf-8")
            req.add_header("Authorization", f"Bearer {_BEARER}")
            with urllib.request.urlopen(req, timeout=15) as resp:
                body = json.loads(resp.read())
            if body.get("ok"):
                on_done(True, _("Message envoyé. Merci pour votre retour !"))
            else:
                on_done(False, body.get("message", _("Erreur inconnue.")))
        except urllib.error.HTTPError as exc:
            try:
                body = json.loads(exc.read())
                on_done(False, body.get("message", _("Erreur HTTP {code}.").format(code=exc.code)))
            except Exception:
                on_done(False, _("Erreur HTTP {code}.").format(code=exc.code))
        except Exception as exc:
            on_done(False, str(exc))

    threading.Thread(target=_run, daemon=True).start()
