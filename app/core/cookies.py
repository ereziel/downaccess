"""
Support cookies depuis le navigateur Chromium de l'utilisateur.

Utilise le mécanisme intégré de yt-dlp `cookiesfrombrowser` pour
lire les cookies depuis Chrome, Edge ou Brave.
"""
import logging

from app.core.browser import find_browser, browser_name

_log = logging.getLogger("downaccess.cookies")

# Mapping nom lisible → identifiant yt-dlp
_YTDLP_BROWSER = {
    "Chrome": "chrome",
    "Edge": "edge",
    "Brave": "brave",
}


def apply_cookies(opts: dict) -> None:
    """
    Ajoute l'option cookiesfrombrowser aux options yt-dlp
    pour utiliser les cookies du navigateur de l'utilisateur.
    """
    path = find_browser()
    if not path:
        _log.warning("Aucun navigateur Chromium trouvé pour les cookies")
        return

    name = browser_name(path)
    browser_id = _YTDLP_BROWSER.get(name, "chrome")
    opts["cookiesfrombrowser"] = (browser_id,)
    _log.debug("Cookies %s configurés pour yt-dlp", name)
