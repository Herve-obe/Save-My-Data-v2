"""
comparator.py — Comparaison bit-à-bit des fichiers source/cible via xxHash (xxh3).

Stratégie de comparaison (équilibre vitesse / fiabilité) :
  1. Fichier absent de la cible              → NEW    (pas de hash)
  2. Tailles différentes                     → MODIFIED (pas de hash)
  3. Taille identique ET mtime identique     → UNCHANGED (on fait confiance aux métadonnées)
  4. Taille identique MAIS mtime différent   → hash les deux fichiers pour trancher
  5. Fichier absent de la source             → ORPHAN
"""

import xxhash
from pathlib import Path
from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable

from .scanner import FileEntry, scan_disk

CHUNK_SIZE = 4 * 1024 * 1024  # 4 Mo par lecture (optimal pour xxh3)

# Extension réservée aux copies atomiques temporaires de copy_engine.
# Ces fichiers ne doivent jamais apparaître comme orphelins (résidu de crash).
_INTERNAL_TEMP_EXT = [".smd_tmp"]


class FileStatus(Enum):
    NEW       = auto()   # Présent sur la source, absent de la cible → à copier
    MODIFIED  = auto()   # Contenu différent entre source et cible    → à remplacer
    UNCHANGED = auto()   # Identique des deux côtés                   → rien à faire
    ORPHAN    = auto()   # Absent de la source, présent sur la cible  → à réviser


@dataclass
class CompareResult:
    """Résultat de la comparaison pour un fichier."""
    source_entry: FileEntry | None   # None uniquement pour les ORPHAN
    target_path: Path
    status: FileStatus


def hash_file(path: Path) -> str | None:
    """
    Calcule le hash xxh3_64 d'un fichier chunk par chunk.
    Retourne None si le fichier est inaccessible.
    """
    h = xxhash.xxh3_64()
    try:
        with open(path, 'rb') as f:
            while chunk := f.read(CHUNK_SIZE):
                h.update(chunk)
        return h.hexdigest()
    except (PermissionError, FileNotFoundError, OSError):
        return None


def compare(
    source_root: Path,
    target_root: Path,
    excluded_extensions: list[str] | None = None,
    excluded_folders: list[str] | None = None,
    max_size_bytes: int = 0,
    progress_callback: Callable[[int, int], None] | None = None,
) -> list[CompareResult]:
    """
    Compare tous les fichiers entre le disque source et le disque cible.

    Args:
        source_root:          Racine du disque source.
        target_root:          Racine du dossier de sauvegarde sur le disque cible.
        excluded_extensions:  Extensions à ignorer lors du scan source.
        excluded_folders:     Dossiers à ignorer lors du scan source.
        max_size_bytes:       Taille max (0 = pas de limite).
        progress_callback:    Appelé avec (fichiers_traités, total_estimé).

    Returns:
        Liste de CompareResult pour chaque fichier nécessitant une action
        ou identifié comme orphelin.
    """
    # ── Indexation de la source ──────────────────────────────────────────────
    source_index: dict[Path, FileEntry] = {}
    for entry in scan_disk(source_root, excluded_extensions, excluded_folders, max_size_bytes):
        source_index[entry.relative_path] = entry

    # ── Indexation de la cible ───────────────────────────────────────────────
    # Les fichiers .smd_tmp sont des copies atomiques partielles (résidus de crash).
    # Les exclure évite qu'ils remontent comme orphelins à la révision suivante.
    target_index: dict[Path, FileEntry] = {}
    if target_root.exists():
        for entry in scan_disk(target_root, excluded_extensions=_INTERNAL_TEMP_EXT):
            target_index[entry.relative_path] = entry

    results: list[CompareResult] = []
    total = len(source_index)
    done = 0

    # ── Comparaison source → cible ───────────────────────────────────────────
    for rel_path, src in source_index.items():
        target_path = target_root / rel_path

        if rel_path not in target_index:
            # Cas 1 : fichier absent de la cible
            results.append(CompareResult(src, target_path, FileStatus.NEW))

        else:
            tgt = target_index[rel_path]

            if src.size != tgt.size:
                # Cas 2 : tailles différentes → forcément modifié
                results.append(CompareResult(src, target_path, FileStatus.MODIFIED))

            elif abs(src.mtime - tgt.mtime) < 2.0:
                # Cas 3 : taille et mtime identiques → inchangé (tolérance 2s pour FAT32)
                results.append(CompareResult(src, target_path, FileStatus.UNCHANGED))

            else:
                # Cas 4 : même taille mais mtime différent → on hash pour trancher
                src_hash = hash_file(src.path)
                tgt_hash = hash_file(target_path)

                if src_hash is None or tgt_hash is None or src_hash != tgt_hash:
                    results.append(CompareResult(src, target_path, FileStatus.MODIFIED))
                else:
                    results.append(CompareResult(src, target_path, FileStatus.UNCHANGED))

        done += 1
        if progress_callback:
            progress_callback(done, total)

    # ── Détection des orphelins (présents sur cible, absents de la source) ───
    for rel_path, tgt in target_index.items():
        if rel_path not in source_index:
            results.append(CompareResult(None, tgt.path, FileStatus.ORPHAN))

    return results
