"""
Résolution du chemin ffmpeg.
Priorité :
  1. Chemin configuré par l'utilisateur (Préférences → Avancé)
  2. Bundle PyInstaller : _internal/ffmpeg.exe (à côté de l'exe)
  3. Développement : assets/ffmpeg.exe (voir scripts/update_ffmpeg.py)
  4. imageio-ffmpeg (fallback legacy)
  5. ffmpeg dans le PATH
"""
import sys
from pathlib import Path


def get_ffmpeg_path(settings: dict) -> str:
    """Retourne le chemin vers ffmpeg à utiliser."""
    configured = settings.get("ffmpeg_path", "").strip()
    if configured and configured != "ffmpeg":
        return configured

    # Bundle PyInstaller (one-dir) : ffmpeg.exe est dans _internal/
    if getattr(sys, "frozen", False):
        bundled = Path(sys.executable).parent / "_internal" / "ffmpeg.exe"
        if bundled.exists():
            return str(bundled)

    # Développement : assets/ffmpeg.exe
    dev_path = Path(__file__).parent.parent.parent / "assets" / "ffmpeg.exe"
    if dev_path.exists():
        return str(dev_path)

    # Fallback legacy imageio-ffmpeg
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass

    return "ffmpeg"


def get_ffplay_path() -> str:
    """Retourne le chemin vers ffplay à utiliser."""
    # Bundle PyInstaller (one-dir) : ffplay.exe est dans _internal/
    if getattr(sys, "frozen", False):
        bundled = Path(sys.executable).parent / "_internal" / "ffplay.exe"
        if bundled.exists():
            return str(bundled)

    # Développement : assets/ffplay.exe
    dev_path = Path(__file__).parent.parent.parent / "assets" / "ffplay.exe"
    if dev_path.exists():
        return str(dev_path)

    return "ffplay"
