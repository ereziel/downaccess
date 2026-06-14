# -*- mode: python ; coding: utf-8 -*-
"""
Spec PyInstaller pour DownAccess.
Build : uv run pyinstaller downaccess.spec  (ou : uv run python scripts/build.py)
"""
import sys
from pathlib import Path

block_cipher = None

# Binaires embarqués (voir scripts/update_ffmpeg.py)
FFMPEG_EXE = Path('assets/ffmpeg.exe')
if not FFMPEG_EXE.exists():
    raise FileNotFoundError(
        f"{FFMPEG_EXE} introuvable.\n"
        "Lance d'abord : python scripts/update_ffmpeg.py"
    )

# Moteur JavaScript (QuickJS-ng) requis par yt-dlp pour resoudre le challenge
# de signature YouTube (voir scripts/update_jsruntime.py).
QJS_EXE = Path('assets/qjs.exe')
if not QJS_EXE.exists():
    raise FileNotFoundError(
        f"{QJS_EXE} introuvable.\n"
        "Lance d'abord : python scripts/update_jsruntime.py"
    )

# Catalogues de traduction (gettext .po pour chaque langue supportee).
# Le runtime app/core/i18n.py les charge via polib depuis _internal/locales/.
LOCALE_DATAS = []
for po_path in Path('locales').rglob('*.po'):
    # Ex : locales/en/LC_MESSAGES/base.po -> locales/en/LC_MESSAGES
    LOCALE_DATAS.append((str(po_path), str(po_path.parent)))

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[
        (str(FFMPEG_EXE), '.'),   # → _internal/ffmpeg.exe dans le bundle
        (str(QJS_EXE), '.'),      # → _internal/qjs.exe dans le bundle
    ],
    datas=LOCALE_DATAS,
    hiddenimports=[
        # wxPython
        'wx',
        'wx._core',
        'wx.html2',
        'wx.media',
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
        # i18n (lecture des .po au runtime)
        'polib',
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
