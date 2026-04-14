"""
restore_engine.py — Moteur de restauration depuis la sauvegarde.

Workflow :
    1. find_backup()  → localise la copie dans le disque de sauvegarde
    2. restore()      → envoie le fichier actuel à la Corbeille, puis restaure

La Corbeille garantit que l'utilisateur peut toujours annuler l'opération.
"""

import shutil
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime

import send2trash

from .path_utils import target_folder_name


# ── Types de résultats ────────────────────────────────────────────────────────

@dataclass
class RestoreCandidate:
    """Sauvegarde trouvée pour un fichier ou dossier source."""
    source_path:  Path       # Chemin demandé (sur le disque source)
    backup_path:  Path       # Chemin dans la sauvegarde
    backup_mtime: datetime   # Date de la dernière sauvegarde
    size:         int        # Taille en octets (0 pour les dossiers)
    is_dir:       bool       # True si c'est un dossier


@dataclass
class RestoreResult:
    """Résultat d'une opération de restauration."""
    success:        bool
    restored_count: int                        # Fichiers restaurés
    sent_to_trash:  list[Path] = field(default_factory=list)
    errors:         list[tuple[Path, str]] = field(default_factory=list)


# ── Recherche de sauvegarde ───────────────────────────────────────────────────

def find_backup(
    source_path: Path,
    source_disks: list[Path],
    target_disk: Path,
) -> RestoreCandidate | None:
    """
    Cherche la copie de sauvegarde d'un fichier ou dossier.

    Algorithme :
        Pour chaque disque source configuré (ex. C:\\, D:\\) :
            Si source_path est sous ce disque :
                Calcule le chemin de sauvegarde correspondant
                Ex. C:\\Users\\herve\\doc.pdf
                  → BackUp\\[C]\\Users\\herve\\doc.pdf

    Returns:
        RestoreCandidate si une sauvegarde existe, None sinon.
    """
    for source_root in source_disks:
        try:
            rel_path = source_path.relative_to(source_root)
        except ValueError:
            continue  # Ce fichier n'est pas sous ce disque source

        backup_path = target_disk / target_folder_name(source_root) / rel_path

        if backup_path.exists():
            stat = backup_path.stat()
            return RestoreCandidate(
                source_path=source_path,
                backup_path=backup_path,
                backup_mtime=datetime.fromtimestamp(stat.st_mtime),
                size=stat.st_size if backup_path.is_file() else _dir_size(backup_path),
                is_dir=backup_path.is_dir(),
            )

    return None


# ── Restauration ──────────────────────────────────────────────────────────────

def restore(
    candidate: RestoreCandidate,
    destination: Path | None = None,
) -> RestoreResult:
    """
    Restaure un fichier ou dossier depuis la sauvegarde.

    Étapes :
        1. Si un fichier/dossier existe à la destination :
               → l'envoyer à la Corbeille (undo possible)
        2. Copier depuis la sauvegarde vers la destination

    Args:
        candidate:   Résultat de find_backup().
        destination: Destination de restauration.
                     None = emplacement d'origine (candidate.source_path).
    """
    dst = destination if destination is not None else candidate.source_path
    sent_to_trash: list[Path] = []
    errors: list[tuple[Path, str]] = []

    # ── Étape 1 : Envoyer le fichier actuel à la Corbeille ───────────────────
    if dst.exists():
        try:
            send2trash.send2trash(str(dst))
            sent_to_trash.append(dst)
        except Exception as exc:
            errors.append((dst, f"Impossible d'envoyer à la Corbeille : {exc}"))
            return RestoreResult(False, 0, sent_to_trash, errors)

    # ── Étape 2 : Copier depuis la sauvegarde ────────────────────────────────
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)

        if candidate.is_dir:
            shutil.copytree(str(candidate.backup_path), str(dst))
        else:
            shutil.copy2(str(candidate.backup_path), str(dst))

        return RestoreResult(True, 1, sent_to_trash, [])

    except PermissionError as exc:
        errors.append((candidate.backup_path, f"Permission refusée : {exc}"))
    except OSError as exc:
        errors.append((candidate.backup_path, str(exc)))

    return RestoreResult(False, 0, sent_to_trash, errors)


def restore_many(
    candidates: list[RestoreCandidate],
    destination_dir: Path | None = None,
) -> RestoreResult:
    """
    Restaure plusieurs fichiers/dossiers en un seul appel.

    Args:
        candidates:      Liste de RestoreCandidate.
        destination_dir: Si fourni, tous les fichiers sont restaurés dans ce
                         dossier (en conservant leurs noms). Si None, chacun
                         est restauré à son emplacement d'origine.
    """
    total_restored = 0
    all_trash: list[Path] = []
    all_errors: list[tuple[Path, str]] = []

    for cand in candidates:
        dst = (destination_dir / cand.source_path.name) if destination_dir else None
        result = restore(cand, dst)
        total_restored += result.restored_count
        all_trash.extend(result.sent_to_trash)
        all_errors.extend(result.errors)

    return RestoreResult(
        success=total_restored > 0,
        restored_count=total_restored,
        sent_to_trash=all_trash,
        errors=all_errors,
    )


# ── Utilitaires ───────────────────────────────────────────────────────────────

def _dir_size(path: Path) -> int:
    """Calcule la taille totale d'un dossier (récursif)."""
    total = 0
    try:
        for f in path.rglob("*"):
            if f.is_file():
                try:
                    total += f.stat().st_size
                except OSError:
                    pass
    except OSError:
        pass
    return total
