"""
Logging persistant DownAccess.
Fichier tournant dans %APPDATA%/DownAccess/downaccess.log (1 Mo, 1 backup).
"""
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


def _log_path() -> Path:
    appdata = os.environ.get("APPDATA", str(Path.home()))
    d = Path(appdata) / "DownAccess"
    d.mkdir(parents=True, exist_ok=True)
    return d / "downaccess.log"


def setup() -> logging.Logger:
    """Configure et retourne le logger racine 'downaccess'. Idempotent."""
    logger = logging.getLogger("downaccess")
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)
    handler = RotatingFileHandler(
        _log_path(),
        maxBytes=1_000_000,
        backupCount=1,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    ))
    logger.addHandler(handler)
    return logger


def get_log_path() -> Path:
    return _log_path()
