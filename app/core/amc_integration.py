r"""
Passerelle vers Access Media Converter (AMC).

DownAccess télécharge ; AMC convertit. Comme Downie ouvre un fichier dans Permute,
on ouvre le fichier téléchargé dans AMC pour une conversion avancée.

AMC accepte un chemin de fichier en argument de ligne de commande et gère lui-même
l'instance unique (un fichier déposé alors qu'AMC est déjà ouvert est relayé vers la
fenêtre existante). DownAccess n'a donc qu'à lancer l'exécutable avec le chemin.

Résolution de l'exécutable, par priorité :
  1. Chemin configuré par l'utilisateur (Préférences → Avancé)
  2. Registre de désinstallation Inno Setup (InstallLocation de l'AppId d'AMC)
  3. Chemin d'installation par défaut (%ProgramFiles%\Accessible Media Converter)
"""
import os
import subprocess
from pathlib import Path

_AMC_EXE = "AccessibleMediaConverter.exe"

# AppId Inno Setup d'AMC (cf. UniversalTranscoder/core/app_info.py). La clé de
# désinstallation Inno est "<AppId>_is1".
_AMC_APP_ID = "{7E285383-842B-4F3B-8455-DF3F9F74F4F7}"
_AMC_UNINSTALL_KEY = (
    r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
    "\\" + _AMC_APP_ID + "_is1"
)

# Page de téléchargement, proposée si AMC n'est pas détecté.
AMC_RELEASES_URL = "https://github.com/math65/accessible-media-converter/releases"


def _from_registry() -> str | None:
    """Lit InstallLocation dans le registre de désinstallation Inno d'AMC.

    Essaie les deux vues du registre (64 puis 32 bits) pour couvrir un installeur
    quelle que soit son architecture. Renvoie le chemin de l'exe s'il existe.
    """
    try:
        import winreg
    except ImportError:
        return None

    for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, _AMC_UNINSTALL_KEY, 0,
                winreg.KEY_READ | view,
            ) as key:
                location, _type = winreg.QueryValueEx(key, "InstallLocation")
        except OSError:
            continue
        if location:
            candidate = Path(location) / _AMC_EXE
            if candidate.exists():
                return str(candidate)
    return None


def find_amc_executable(settings: dict) -> str | None:
    """Retourne le chemin de l'exécutable AMC, ou None s'il est introuvable."""
    configured = (settings.get("amc_path") or "").strip()
    if configured and os.path.exists(configured):
        return configured

    from_reg = _from_registry()
    if from_reg:
        return from_reg

    program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    default = Path(program_files) / "Accessible Media Converter" / _AMC_EXE
    if default.exists():
        return str(default)

    return None


def open_in_amc(filepath: str, settings: dict) -> bool:
    """Lance AMC avec le fichier donné. Renvoie True si AMC a été lancé.

    Renvoie False si l'exécutable est introuvable ou si le lancement échoue ;
    l'appelant (UI) affiche alors le message d'aide approprié.
    """
    exe = find_amc_executable(settings)
    if not exe or not filepath:
        return False
    try:
        subprocess.Popen([exe, filepath])
        return True
    except OSError:
        return False
