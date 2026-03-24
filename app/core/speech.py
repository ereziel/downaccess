"""
Module de synthèse vocale pour lecteurs d'écran (NVDA, JAWS, etc.).
Utilise accessible_output2 — ne bloque jamais l'UI.
Toutes les fonctions sont silencieuses si aucun lecteur d'écran n'est actif.
"""

import ctypes

_speaker = None
_available = False

try:
    from accessible_output2.outputs.auto import Auto as _Auto
    _speaker = _Auto()
    _available = True
except Exception:
    pass


def _screen_reader_active() -> bool:
    """Vérifie si un lecteur d'écran est réellement actif (NVDA, JAWS, etc.)."""
    try:
        # NVDA : tester si le client NVDA est chargé
        try:
            ctypes.windll.LoadLibrary("nvdaControllerClient.dll")
            res = ctypes.windll.nvdaControllerClient.nvdaController_testIfRunning()
            if res == 0:
                return True
        except (OSError, AttributeError):
            pass

        # JAWS : tester si la fenêtre Freedom Scientific est présente
        try:
            jaws_running = ctypes.windll.user32.FindWindowW("JABORUNTIME", None)
            if jaws_running:
                return True
        except (OSError, AttributeError):
            pass

        # Narrator : API SystemParametersInfo SPI_GETSCREENREADER
        try:
            pvParam = ctypes.c_int(0)
            ctypes.windll.user32.SystemParametersInfoW(
                0x0046, 0, ctypes.byref(pvParam), 0  # SPI_GETSCREENREADER
            )
            if pvParam.value:
                return True
        except (OSError, AttributeError):
            pass

        return False
    except Exception:
        return False


def speak(text: str, interrupt: bool = True) -> None:
    """
    Parle le texte via le lecteur d'écran actif.
    interrupt=True coupe la parole en cours avant d'annoncer.
    """
    if not _available or not _speaker:
        return
    if not _screen_reader_active():
        return
    try:
        _speaker.speak(text, interrupt=interrupt)
    except Exception:
        pass


def braille(text: str) -> None:
    """Envoie le texte sur la plage braille si disponible."""
    if not _available or not _speaker:
        return
    if not _screen_reader_active():
        return
    try:
        _speaker.braille(text)
    except Exception:
        pass
