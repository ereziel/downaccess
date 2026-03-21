"""
Module de synthèse vocale pour lecteurs d'écran (NVDA, JAWS, etc.).
Utilise accessible_output2 — ne bloque jamais l'UI.
Toutes les fonctions sont silencieuses si aucun lecteur d'écran n'est actif.
"""

try:
    from accessible_output2.outputs.auto import Auto as _Auto
    _speaker = _Auto()
    _available = True
except Exception:
    _speaker = None
    _available = False


def speak(text: str, interrupt: bool = True) -> None:
    """
    Parle le texte via le lecteur d'écran actif.
    interrupt=True coupe la parole en cours avant d'annoncer.
    """
    if not _available or not _speaker:
        return
    try:
        _speaker.speak(text, interrupt=interrupt)
    except Exception:
        pass


def braille(text: str) -> None:
    """Envoie le texte sur la plage braille si disponible."""
    if not _available or not _speaker:
        return
    try:
        _speaker.braille(text)
    except Exception:
        pass
