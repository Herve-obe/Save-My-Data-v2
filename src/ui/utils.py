"""
utils.py — Utilitaires UI partagés pour Save My Data.

Centralise les fonctions de formatage et de chargement utilisées par
plusieurs modules UI afin d'éviter la duplication et les incohérences.
"""

import json
from pathlib import Path


def fmt_size(size: int) -> str:
    """
    Formate une taille en octets en chaîne lisible par l'humain.

    Exemples :
        fmt_size(512)          → '512 o'
        fmt_size(2048)         → '2.0 Ko'
        fmt_size(1_500_000)    → '1.4 Mo'
        fmt_size(5_000_000_000)→ '4.7 Go'
    """
    if size < 1024:
        return f"{size} o"
    if size < 1024 ** 2:
        return f"{size / 1024:.1f} Ko"
    if size < 1024 ** 3:
        return f"{size / 1024 ** 2:.1f} Mo"
    return f"{size / 1024 ** 3:.1f} Go"


def fmt_duration(seconds: float) -> str:
    """
    Formate une durée en secondes en chaîne lisible.

    Exemples :
        fmt_duration(5)    → '5s'
        fmt_duration(75)   → '1m 15s'
        fmt_duration(3661) → '1h 01m 01s'
    """
    seconds = max(0.0, seconds)
    if seconds < 60:
        return f"{seconds:.0f}s"
    if seconds < 3600:
        m = int(seconds // 60)
        s = int(seconds % 60)
        return f"{m}m {s:02d}s"
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h}h {m:02d}m {s:02d}s"


def load_last_backup(data_dir: Path) -> "dict | None":
    """
    Charge le fichier data/last_backup.json.
    Retourne le dict ou None si absent ou illisible.
    Partagé entre DashboardPage et HistoryPage pour éviter la duplication.
    """
    p = data_dir / "last_backup.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return None
