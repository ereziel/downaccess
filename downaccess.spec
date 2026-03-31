# -*- mode: python ; coding: utf-8 -*-
"""
Spec PyInstaller pour DownAccess.
Build : source venv/Scripts/activate && pyinstaller downaccess.spec
"""
import sys
from pathlib import Path

block_cipher = None

# Binaires embarqués (voir scripts/update_ffmpeg.py)
FFMPEG_EXE = Path('assets/ffmpeg.exe')
FFPLAY_EXE = Path('assets/ffplay.exe')
for _bin in (FFMPEG_EXE, FFPLAY_EXE):
    if not _bin.exists():
        raise FileNotFoundError(
            f"{_bin} introuvable.\n"
            "Lance d'abord : python scripts/update_ffmpeg.py"
        )

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[
        (str(FFMPEG_EXE), '.'),   # → _internal/ffmpeg.exe dans le bundle
        (str(FFPLAY_EXE), '.'),   # → _internal/ffplay.exe dans le bundle
    ],
    datas=[],
    hiddenimports=[
        # wxPython
        'wx',
        'wx._core',
        'wx.html2',
        # accessible_output2
        'accessible_output2',
        'accessible_output2.outputs',
        'accessible_output2.outputs.auto',
        'accessible_output2.outputs.nvda',
        'accessible_output2.outputs.sapi5',
        # yt-dlp
        'yt_dlp',
        'yt_dlp.extractor',
        'yt_dlp.extractor._extractors',
        'yt_dlp.postprocessor',
        # Divers
        'certifi',
        'urllib3',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'PIL',
        'scipy',
        'pandas',
        'IPython',
        'notebook',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='DownAccess',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # Pas de fenêtre console
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon='assets/icon.ico',  # Décommenter quand l'icône sera créée
    version='version_info.txt',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='DownAccess',
)
