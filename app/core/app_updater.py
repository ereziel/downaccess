"""
Mise à jour automatique de DownAccess.

Flux :
1. Interroger l'API GitHub pour la dernière release
2. Comparer avec la version installée
3. Si nouvelle version : télécharger DownAccess-Setup.exe dans %TEMP%
4. Lancer l'installeur et fermer l'app
"""
import os
import subprocess
import tempfile
import threading
import urllib.request
import urllib.error
import json

from app.version import __version__

GITHUB_API = "https://api.github.com/repos/math65/downaccess/releases/latest"
ASSET_NAME = "DownAccess-Setup.exe"
_UA = "DownAccess-Updater"


def _parse_version(tag: str) -> tuple[int, ...]:
    """'v0.2.1' ou '0.2.1' → (0, 2, 1)"""
    tag = tag.lstrip("v").strip()
    try:
        return tuple(int(x) for x in tag.split("."))
    except Exception:
        return (0,)


def check_for_update(on_done) -> None:
    """
    Lance la vérification en arrière-plan.
    on_done(status, info) appelé dans le thread secondaire — utiliser wx.CallAfter.
      status : "up_to_date" | "update_available" | "error"
      info   : nouvelle version (str) ou message d'erreur
    """
    def _run():
        try:
            req = urllib.request.Request(GITHUB_API)
            req.add_header("User-Agent", _UA)
            req.add_header("Accept", "application/vnd.github+json")
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read())

            tag      = data.get("tag_name", "")
            new_ver  = tag.lstrip("v").strip()
            if not new_ver:
                on_done("error", "Réponse GitHub invalide.")
                return

            if _parse_version(new_ver) > _parse_version(__version__):
                on_done("update_available", new_ver)
            else:
                on_done("up_to_date", __version__)

        except urllib.error.URLError:
            on_done("error", "Impossible de contacter GitHub.")
        except Exception as exc:
            on_done("error", str(exc))

    threading.Thread(target=_run, daemon=True).start()


def download_and_install(new_version: str, on_progress, on_error) -> None:
    """
    Télécharge DownAccess-Setup.exe depuis la release GitHub,
    le lance puis ferme l'app.

    on_progress(percent: float)  — appelé dans le thread secondaire
    on_error(message: str)       — appelé dans le thread secondaire
    """
    def _run():
        dest = os.path.join(tempfile.gettempdir(), ASSET_NAME)
        # URL directe de l'asset (même nom à chaque release)
        asset_url = (
            f"https://github.com/math65/downaccess/releases/latest/download/{ASSET_NAME}"
        )
        try:
            req = urllib.request.Request(asset_url)
            req.add_header("User-Agent", _UA)
            with urllib.request.urlopen(req, timeout=30) as resp:
                total = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                chunk = 65536  # 64 Ko
                with open(dest, "wb") as f:
                    while True:
                        buf = resp.read(chunk)
                        if not buf:
                            break
                        f.write(buf)
                        downloaded += len(buf)
                        if total:
                            on_progress(downloaded / total * 100)

            # Lancer l'installeur
            subprocess.Popen([dest], shell=True)
            # Quitter l'app pour que l'installeur puisse remplacer les fichiers
            import wx
            wx.CallAfter(wx.GetApp().ExitMainLoop)

        except Exception as exc:
            on_error(str(exc))

    threading.Thread(target=_run, daemon=True).start()
