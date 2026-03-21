"""
Résolution du chemin ffmpeg.
Priorité :
  1. Chemin configuré par l'utilisateur (Préférences → Avancé)
  2. Binaire fourni par imageio-ffmpeg (inclus dans le package)
  3. ffmpeg dans le PATH (fallback)
"""


def get_ffmpeg_path(settings: dict) -> str:
    """Retourne le chemin vers ffmpeg à utiliser."""
    configured = settings.get("ffmpeg_path", "").strip()
    if configured and configured != "ffmpeg":
        return configured

    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass

    return "ffmpeg"
