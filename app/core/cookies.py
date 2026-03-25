"""
Support cookies depuis le navigateur Chrome de l'utilisateur.

Utilise le mécanisme intégré de yt-dlp `cookiesfrombrowser` pour
lire les cookies directement depuis le profil Chrome par défaut.
"""
import logging

_log = logging.getLogger("downaccess.cookies")


def apply_cookies(opts: dict) -> None:
    """
    Ajoute l'option cookiesfrombrowser aux options yt-dlp
    pour utiliser les cookies du navigateur Chrome de l'utilisateur.
    """
    opts["cookiesfrombrowser"] = ("chrome",)
    _log.debug("Cookies Chrome configurés pour yt-dlp")
