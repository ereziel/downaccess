"""
Résolution du moteur JavaScript pour yt-dlp.

Depuis 2026, yt-dlp EXIGE un moteur JS externe pour résoudre le challenge de
signature/`n` de YouTube (sinon « Only images available » / « Requested format
is not available »). On embarque QuickJS-ng (`qjs.exe`, ~2 Mo) — le solveur
`yt-dlp-ejs` est déjà fourni par yt-dlp, il ne manque que l'exécutable.

Priorité :
  1. Bundle PyInstaller : _internal/qjs.exe (à côté de l'exe)
  2. Développement : assets/qjs.exe (voir scripts/update_jsruntime.py)
  3. Aucun -> repli sur la détection système par yt-dlp (node/deno/quickjs)
"""
import sys
from pathlib import Path


def get_js_runtime_path() -> str | None:
    """Chemin du qjs.exe embarqué, ou None si introuvable."""
    if getattr(sys, "frozen", False):
        bundled = Path(sys.executable).parent / "_internal" / "qjs.exe"
        if bundled.exists():
            return str(bundled)

    dev_path = Path(__file__).parent.parent.parent / "assets" / "qjs.exe"
    if dev_path.exists():
        return str(dev_path)

    return None


def get_js_runtimes_opt() -> dict:
    """Valeur pour l'option yt-dlp `js_runtimes`.

    Si QuickJS est embarqué, on le désigne explicitement par son chemin.
    Sinon (dev sans qjs), on laisse yt-dlp chercher un runtime système.
    """
    path = get_js_runtime_path()
    if path:
        return {"quickjs": {"path": path}}
    return {"node": {}, "deno": {}, "quickjs": {}}
