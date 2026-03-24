"""
Support cookies depuis le profil WebView2 persistent.

Utilise le mécanisme intégré de yt-dlp `cookiesfrombrowser` avec le
navigateur "chromium" et le chemin du profil WebView2 comme profile.
"""
import logging
import os
from pathlib import Path

_log = logging.getLogger("downaccess.cookies")


def _webview_profile_dir() -> Path:
    """Retourne le dossier du profil WebView2 (contient Default/)."""
    appdata = os.environ.get("APPDATA", str(Path.home()))
    return Path(appdata) / "DownAccess" / "WebView2Profile" / "EBWebView"


def apply_cookies(opts: dict) -> None:
    """
    Ajoute l'option cookiesfrombrowser aux options yt-dlp
    pour utiliser les cookies du profil WebView2 intégré.
    """
    profile_dir = _webview_profile_dir()
    cookies_db = profile_dir / "Default" / "Network" / "Cookies"

    if not cookies_db.exists():
        _log.debug("Cookie DB introuvable : %s", cookies_db)
        return

    # yt-dlp accepte un chemin comme "profile" si c'est un path absolu
    # Il cherchera le fichier Cookies dans ce dossier
    default_dir = str(profile_dir / "Default")
    opts["cookiesfrombrowser"] = ("chromium", default_dir, None, None)
    _log.debug("Cookies WebView2 configurés depuis : %s", default_dir)
