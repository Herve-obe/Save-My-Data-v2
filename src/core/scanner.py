"""
scanner.py — Parcourt récursivement un disque source et retourne la liste des fichiers.
"""

import os
from pathlib import Path
from dataclasses import dataclass
from typing import Generator


@dataclass
class FileEntry:
    """Représente un fichier trouvé lors du scan."""
    path: Path            # Chemin absolu du fichier
    relative_path: Path   # Chemin relatif depuis la racine du disque source
    size: int             # Taille en octets
    mtime: float          # Date de modification (timestamp Unix)


def scan_disk(
    root: Path,
    excluded_extensions: list[str] | None = None,
    excluded_folders: list[str] | None = None,
    max_size_bytes: int = 0,
) -> Generator[FileEntry, None, None]:
    """
    Parcourt récursivement un disque/dossier et yield un FileEntry par fichier.

    Args:
        root:                 Dossier racine à scanner.
        excluded_extensions:  Extensions à ignorer (ex. ['.tmp', '.log']).
        excluded_folders:     Noms de dossiers à ignorer (ex. ['node_modules']).
        max_size_bytes:       Taille max en octets (0 = pas de limite).
    """
    excl_ext = {e.lower().lstrip('.') for e in (excluded_extensions or [])}
    excl_dir = {f.lower() for f in (excluded_folders or [])}

    for dirpath, dirnames, filenames in os.walk(root, topdown=True, onerror=_on_error):
        current = Path(dirpath)

        # Exclure les sous-dossiers filtrés (modifie dirnames en place pour éviter d'y descendre)
        dirnames[:] = [
            d for d in dirnames
            if d.lower() not in excl_dir
        ]

        for filename in filenames:
            filepath = current / filename

            # Filtrer par extension ou par nom de fichier complet
            # (ex. ".tmp" → extension, "Thumbs.db" ou ".DS_Store" → nom entier)
            suffix = filepath.suffix.lower().lstrip('.')
            filename_normed = filename.lower().lstrip('.')
            if suffix in excl_ext or filename_normed in excl_ext:
                continue

            try:
                stat = filepath.stat()
            except (PermissionError, FileNotFoundError, OSError):
                continue

            # Filtrer par taille maximale
            if max_size_bytes > 0 and stat.st_size > max_size_bytes:
                continue

            yield FileEntry(
                path=filepath,
                relative_path=filepath.relative_to(root),
                size=stat.st_size,
                mtime=stat.st_mtime,
            )


def _on_error(error: OSError) -> None:
    """Ignore silencieusement les erreurs de permission lors du scan."""
    pass
