"""
config.py — Chargement et sauvegarde des paramètres utilisateur.

Chemins :
    Mode développement  → <racine_projet>/config/settings.json
    Mode frozen (.exe)  → %APPDATA%/SaveMyData/config/settings.json

Le fichier settings.json est lu une seule fois puis mis en cache.
Utilisez config.load() pour obtenir le dict complet,
ou config.get('backup.mode') pour un accès par clé pointée.
"""

import copy
import json
import os
import sys
from pathlib import Path
from typing import Any


def _get_app_base_dir() -> Path:
    """
    Retourne le répertoire de base de l'application.

    En mode frozen (PyInstaller) : %APPDATA%/SaveMyData
    En développement             : racine du projet (dossier parent de src/)
    """
    if getattr(sys, "frozen", False):
        return Path(os.environ.get("APPDATA", Path.home())) / "SaveMyData"
    return Path(__file__).parent.parent


# Chemins dérivés (calculés une seule fois au démarrage)
_APP_BASE_DIR = _get_app_base_dir()
_CONFIG_PATH  = _APP_BASE_DIR / "config" / "settings.json"

_cache: dict | None = None

# Sentinelle interne : valeur impossible à confondre avec un résultat réel.
# Remplace le test fragile "cfg is default" dans get().
_MISSING = object()


# ── API publique ──────────────────────────────────────────────────────────────

def app_base_dir() -> Path:
    """Retourne le répertoire de base de l'application (dev ou AppData)."""
    return _APP_BASE_DIR


def load() -> dict:
    """
    Retourne la configuration complète (depuis le cache ou le fichier).

    Retourne une copie profonde du cache interne afin d'éviter que
    des mutations externes corrompent silencieusement l'état en mémoire.
    Utiliser set_value() ou save() pour toute modification persistée.
    """
    global _cache
    _ensure_config_exists()
    if _cache is None:
        try:
            _cache = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            _cache = _defaults()
    return copy.deepcopy(_cache)


def reload() -> dict:
    """Force la relecture du fichier (ignore le cache)."""
    global _cache
    _cache = None
    return load()


def save(config: dict) -> None:
    """Sauvegarde la configuration et met à jour le cache."""
    global _cache
    _cache = config
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CONFIG_PATH.write_text(
        json.dumps(config, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def get(key: str, default: Any = None) -> Any:
    """
    Accès à une valeur par clé pointée.

    Exemples :
        config.get('backup.mode')                → 'shutdown'
        config.get('filters.excluded_extensions') → ['.tmp', ...]
        config.get('backup.target_disk', '')      → ''

    Utilise _MISSING comme sentinelle pour distinguer "clé absente"
    de "clé présente avec valeur None" (évite le piège de 'is default').
    """
    cfg = load()
    for part in key.split("."):
        if not isinstance(cfg, dict):
            return default
        val = cfg.get(part, _MISSING)
        if val is _MISSING:
            return default
        cfg = val
    return cfg


def set_value(key: str, value: Any) -> None:
    """Modifie une valeur par clé pointée et sauvegarde."""
    cfg = load()
    parts = key.split(".")
    node = cfg
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node[parts[-1]] = value
    save(cfg)


# ── Initialisation premier lancement ─────────────────────────────────────────

def _ensure_config_exists() -> None:
    """
    Crée settings.json si le fichier n'existe pas encore (premier lancement).

    En mode frozen, tente d'abord de copier le template embarqué dans le
    bundle PyInstaller (_MEIPASS/config/settings.json).
    Sinon, écrit les valeurs par défaut.
    """
    if _CONFIG_PATH.exists():
        return

    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Essayer de copier le template embarqué (mode frozen uniquement)
    if getattr(sys, "frozen", False):
        try:
            import shutil
            template = Path(sys._MEIPASS) / "config" / "settings.json"
            if template.exists():
                shutil.copy(template, _CONFIG_PATH)
                return
        except Exception:
            pass

    # Écrire les valeurs par défaut
    _CONFIG_PATH.write_text(
        json.dumps(_defaults(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ── Valeurs par défaut ────────────────────────────────────────────────────────

def _defaults() -> dict:
    return {
        "version": "1.2.0",
        "autostart": True,
        "theme": "dark",
        "language": "fr",
        "backup": {
            "mode": "shutdown",
            "scheduled_time": "22:00",
            "target_disk": "",
            "source_disks": [],
        },
        "filters": {
            "excluded_extensions": [".tmp", ".log", ".DS_Store", "Thumbs.db"],
            "excluded_folders": [
                "node_modules", "__pycache__", "$RECYCLE.BIN",
                "System Volume Information", ".git",
            ],
            "max_size_bytes": 0,
        },
        "restore": {
            "default_destination": "original",  # 'original' | 'fixed' | 'ask'
            "fixed_folder": "",                  # Dossier fixe de restauration (si mode 'fixed')
            "context_menu": True,
        },
        "ui": {
            "close_behavior": "minimize",
        },
    }
