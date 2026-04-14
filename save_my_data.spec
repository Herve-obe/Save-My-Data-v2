# -*- mode: python ; coding: utf-8 -*-
"""
save_my_data.spec — Fichier de configuration PyInstaller pour Save My Data.

Build :
    pyinstaller save_my_data.spec --clean --noconfirm

Sortie : dist/SaveMyData/SaveMyData.exe  (mode onedir)
"""

import sys
from pathlib import Path

# Répertoire racine du projet (là où se trouve ce .spec)
ROOT = Path(SPECPATH)

block_cipher = None

a = Analysis(
    [str(ROOT / "src" / "main.py")],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=[
        # Template config embarqué → copié dans AppData au premier lancement
        (str(ROOT / "config" / "settings.json"), "config"),
    ],
    hiddenimports=[
        # APScheduler — jobstores / executors chargés dynamiquement
        "apscheduler.schedulers.background",
        "apscheduler.triggers.cron",
        "apscheduler.triggers.date",
        "apscheduler.triggers.interval",
        "apscheduler.executors.pool",
        "apscheduler.jobstores.memory",
        "apscheduler.util",
        # Modules système Windows
        "winreg",
        "ctypes",
        "ctypes.wintypes",
        # Dépendances tiers
        "xxhash",
        "psutil",
        "send2trash",
        # Qt additionnel (SVG pour les icônes éventuelles)
        "PySide6.QtSvg",
        "PySide6.QtXml",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Exclure les gros paquets non utilisés pour alléger le bundle
    excludes=[
        "tkinter", "unittest", "email", "html", "http",
        "xmlrpc", "ftplib", "imaplib", "poplib", "smtplib",
        "sqlite3",
        "numpy", "matplotlib", "scipy", "PIL", "cv2",
        "pandas", "sklearn",
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
    name="SaveMyData",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # Pas de fenêtre console (application GUI)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon="assets/icon.ico",   # Décommentez quand l'icône .ico sera prête
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="SaveMyData",
)
