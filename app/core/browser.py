"""
Détection du navigateur Chromium disponible sur le système.
Utilisé par l'extraction guidée et le dialogue de connexion.
"""
import os

# Chemins classiques Windows (Chrome → Edge → Brave)
_CANDIDATES = [
    # Chrome
    os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
    os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
    os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
    # Edge (présent sur tout Windows 10/11)
    os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
    os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
    # Brave
    os.path.expandvars(r"%ProgramFiles%\BraveSoftware\Brave-Browser\Application\brave.exe"),
    os.path.expandvars(r"%LocalAppData%\BraveSoftware\Brave-Browser\Application\brave.exe"),
]


def find_browser() -> str | None:
    """Retourne le chemin du premier navigateur Chromium trouvé, ou None."""
    for path in _CANDIDATES:
        if os.path.isfile(path):
            return path
    return None


def browser_name(path: str) -> str:
    """Retourne un nom lisible à partir du chemin de l'exécutable."""
    low = path.lower()
    if "chrome" in low:
        return "Chrome"
    if "edge" in low or "msedge" in low:
        return "Edge"
    if "brave" in low:
        return "Brave"
    return "Navigateur"


def downaccess_profile_dir() -> str:
    """Dossier de profil navigateur dédié à DownAccess (persistant).

    L'utilisateur s'y connecte une seule fois via le dialogue de connexion ;
    les cookies y sont conservés et relus par yt-dlp (cookiesfrombrowser).
    Profil isolé = aucun conflit avec le navigateur habituel de l'utilisateur,
    qu'il soit ouvert ou non.
    """
    appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(appdata, "DownAccess", "BrowserProfile")
