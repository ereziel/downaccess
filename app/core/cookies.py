"""
Support cookies depuis le navigateur Chromium de l'utilisateur.

Utilise le mécanisme intégré de yt-dlp `cookiesfrombrowser` pour
lire les cookies depuis Chrome, Edge ou Brave.
"""
import logging
import os

from app.core.browser import browser_name, downaccess_profile_dir, find_browser

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

    # Profil dédié DownAccess : l'utilisateur s'y connecte via le dialogue de
    # connexion. yt-dlp y relit les cookies (chemin du dossier "Default" ;
    # le "Local State" du parent fournit la clé de déchiffrement).
    profile = os.path.join(downaccess_profile_dir(), "Default")
    if os.path.isdir(profile):
        opts["cookiesfrombrowser"] = (browser_id, profile)
        _log.debug("Cookies depuis le profil dédié DownAccess (%s)", name)
    else:
        # Pas encore de profil dédié : repli sur le profil système du navigateur.
        opts["cookiesfrombrowser"] = (browser_id,)
        _log.debug("Cookies depuis le profil système %s (profil dédié absent)", name)
