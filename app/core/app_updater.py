"""
Mise à jour automatique de DownAccess.

Flux :
1. Interroger l'API GitHub pour la dernière release
2. Comparer avec la version installée
3. Si nouvelle version : télécharger DownAccess-Setup.exe dans %TEMP%
4. Vérifier que le fichier est complet (taille > 0)
5. Lancer l'installeur et fermer l'app proprement

Sécurités :
- Téléchargement dans un fichier .tmp, renommé seulement si complet
- Vérification taille fichier > 0 avant lancement
- Timeout réseau strict
- L'app ne se ferme que si le processus installeur a bien démarré
- Aucune exception ne peut crasher l'app silencieusement
"""
import os
import subprocess
import tempfile
import threading
import urllib.request
import urllib.error
import json

from app.version import __version__

GITHUB_API  = "https://api.github.com/repos/math65/downaccess/releases/latest"
ASSET_NAME  = "DownAccess-Setup.exe"
DOWNLOAD_URL = f"https://github.com/math65/downaccess/releases/latest/download/{ASSET_NAME}"
_UA = f"DownAccess/{__version__} (Windows; updater)"


# ---------------------------------------------------------------------------
# Comparaison de versions
# ---------------------------------------------------------------------------

def _parse_version(tag: str) -> tuple[int, ...]:
    """'v0.2.1' ou '0.2.1' → (0, 2, 1)"""
    tag = tag.lstrip("v").strip()
    try:
        return tuple(int(x) for x in tag.split("."))
    except Exception:
        return (0,)


# ---------------------------------------------------------------------------
# Vérification
# ---------------------------------------------------------------------------

def check_for_update(on_done) -> None:
    """
    Vérifie en arrière-plan si une nouvelle version est disponible.
    on_done(status, info, release_notes) est appelé dans le thread — utiliser wx.CallAfter côté UI.
      status        : "up_to_date" | "update_available" | "error"
      info          : nouvelle version (str) ou message d'erreur
      release_notes : notes de version (str) ou ""
    """
    def _run():
        try:
            req = urllib.request.Request(GITHUB_API)
            req.add_header("User-Agent", _UA)
            req.add_header("Accept", "application/vnd.github+json")
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read())

            # Vérifier que la release n'est pas un draft ou pre-release
            if data.get("draft") or data.get("prerelease"):
                on_done("up_to_date", __version__, "")
                return

            tag     = data.get("tag_name", "")
            new_ver = tag.lstrip("v").strip()
            if not new_ver:
                on_done("error", "Réponse GitHub invalide.", "")
                return

            # Vérifier que l'asset existe bien dans cette release
            assets = [a["name"] for a in data.get("assets", [])]
            if ASSET_NAME not in assets:
                on_done("error", f"Asset '{ASSET_NAME}' absent de la release {new_ver}.", "")
                return

            release_notes = data.get("body", "") or ""

            if _parse_version(new_ver) > _parse_version(__version__):
                on_done("update_available", new_ver, release_notes)
            else:
                on_done("up_to_date", __version__, "")

        except urllib.error.URLError:
            on_done("error", "Impossible de contacter GitHub.", "")
        except Exception as exc:
            on_done("error", str(exc), "")

    threading.Thread(target=_run, daemon=True).start()


# ---------------------------------------------------------------------------
# Téléchargement et installation
# ---------------------------------------------------------------------------

def download_and_install(new_version: str, on_progress, on_error) -> None:
    """
    Télécharge l'installeur et le lance.

    on_progress(percent: float)  — progression 0-100
    on_error(message: str)       — appelé si échec ; l'app NE se ferme PAS
    """
    def _run():
        tmp_path  = os.path.join(tempfile.gettempdir(), ASSET_NAME + ".tmp")
        dest_path = os.path.join(tempfile.gettempdir(), ASSET_NAME)

        # Nettoyer un éventuel résidu de téléchargement précédent
        for path in (tmp_path, dest_path):
            try:
                if os.path.exists(path):
                    os.remove(path)
            except OSError:
                pass

        try:
            req = urllib.request.Request(DOWNLOAD_URL)
            req.add_header("User-Agent", _UA)
            with urllib.request.urlopen(req, timeout=60) as resp:
                total      = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                chunk_size = 65536  # 64 Ko
                with open(tmp_path, "wb") as f:
                    while True:
                        buf = resp.read(chunk_size)
                        if not buf:
                            break
                        f.write(buf)
                        downloaded += len(buf)
                        if total > 0:
                            on_progress(downloaded / total * 100)

        except Exception as exc:
            # Supprimer le fichier partiel
            try:
                os.remove(tmp_path)
            except OSError:
                pass
            on_error(f"Téléchargement échoué : {exc}")
            return

        # Vérifier que le fichier n'est pas vide
        size = os.path.getsize(tmp_path)
        if size < 65536:  # Un installeur fait au minimum 64 Ko
            try:
                os.remove(tmp_path)
            except OSError:
                pass
            on_error(f"Fichier téléchargé trop petit ({size} octets) — corrompu ?")
            return

        # Renommer seulement si le téléchargement est complet
        try:
            os.rename(tmp_path, dest_path)
        except OSError as exc:
            on_error(f"Impossible de finaliser le fichier : {exc}")
            return

        # Lancer l'installeur
        try:
            proc = subprocess.Popen([dest_path])
        except Exception as exc:
            on_error(f"Impossible de lancer l'installeur : {exc}")
            return

        # Vérifier que le processus a bien démarré
        if proc.poll() is not None:
            on_error("L'installeur s'est terminé immédiatement — fichier corrompu ?")
            return

        # Tout est bon → fermer l'app proprement
        import wx as _wx
        _wx.CallAfter(_quit_app)

    threading.Thread(target=_run, daemon=True).start()


def _quit_app() -> None:
    """Ferme l'app proprement depuis le thread UI."""
    import wx as _wx
    app = _wx.GetApp()
    if app:
        top = app.GetTopWindow()
        if top:
            top.Close()
        else:
            app.ExitMainLoop()
