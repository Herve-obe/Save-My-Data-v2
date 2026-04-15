"""
copy_engine.py — Copie incrémentale avec écriture atomique.

Écriture atomique : chaque fichier est d'abord écrit dans un fichier
temporaire (.smd_tmp), puis renommé à sa destination finale.
Cela garantit qu'un fichier partiellement écrit (coupure de courant,
disque plein) ne corrompra jamais la sauvegarde.
"""

import shutil
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

from .comparator import CompareResult, FileStatus, compare


@dataclass
class CopyReport:
    """Rapport complet d'une session de sauvegarde."""
    started_at: datetime = field(default_factory=datetime.now)
    finished_at: datetime | None = None

    files_copied: list[Path] = field(default_factory=list)
    bytes_copied: int = 0          # Accumulé pendant la copie (OPTIM-02 : pas de re-stat)
    files_unchanged: int = 0
    orphan_paths: list[Path] = field(default_factory=list)
    errors: list[tuple[Path, str]] = field(default_factory=list)
    cancelled: bool = False

    @property
    def duration_seconds(self) -> float:
        if self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        return 0.0

    def summary(self) -> str:
        mb = self.bytes_copied / (1024 * 1024)
        lines = [
            f"Durée            : {self.duration_seconds:.1f}s",
            f"Fichiers copiés  : {len(self.files_copied)} ({mb:.1f} Mo)",
            f"Inchangés        : {self.files_unchanged}",
            f"Orphelins        : {len(self.orphan_paths)}",
            f"Erreurs          : {len(self.errors)}",
        ]
        if self.cancelled:
            lines.append("⚠ Sauvegarde annulée par l'utilisateur.")
        return "\n".join(lines)


def _atomic_copy(src: Path, dst: Path) -> None:
    """
    Copie src vers dst de manière atomique :
      1. Copie vers dst.smd_tmp (préserve les métadonnées avec copy2)
      2. Renomme .smd_tmp → dst (opération atomique sur le même filesystem)
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(dst.suffix + '.smd_tmp')
    try:
        shutil.copy2(src, tmp)
        tmp.replace(dst)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def _find_existing_ancestor(path: Path) -> Path:
    """
    Remonte l'arborescence jusqu'au premier ancêtre existant.
    Utilisé pour vérifier l'espace disque d'un dossier pas encore créé.
    """
    current = path
    while not current.exists():
        parent = current.parent
        if parent == current:
            break
        current = parent
    return current


def run_backup(
    source_root: Path,
    target_root: Path,
    excluded_extensions: list[str] | None = None,
    excluded_folders: list[str] | None = None,
    max_size_bytes: int = 0,
    progress_callback: Callable[[int, int, str], None] | None = None,
    cancel_check: Callable[[], bool] | None = None,
) -> CopyReport:
    """
    Lance une sauvegarde incrémentale complète de source_root vers target_root.

    Args:
        source_root:          Dossier/disque source à sauvegarder.
        target_root:          Dossier cible dans le disque de sauvegarde.
        excluded_extensions:  Extensions à ignorer.
        excluded_folders:     Dossiers à ignorer.
        max_size_bytes:       Taille max par fichier (0 = pas de limite).
        progress_callback:    Appelé avec (index, total, nom_fichier_courant).
        cancel_check:         Appelé à chaque fichier — retourne True pour annuler.

    Returns:
        CopyReport avec le détail complet de la session.
    """
    report = CopyReport()

    # ── Phase 1 : Scan et comparaison ────────────────────────────────────────
    all_results = compare(
        source_root, target_root,
        excluded_extensions, excluded_folders, max_size_bytes,
    )

    to_copy = [r for r in all_results if r.status in (FileStatus.NEW, FileStatus.MODIFIED)]
    unchanged = [r for r in all_results if r.status == FileStatus.UNCHANGED]
    orphans = [r for r in all_results if r.status == FileStatus.ORPHAN]

    report.files_unchanged = len(unchanged)
    report.orphan_paths = [r.target_path for r in orphans]

    total = len(to_copy)

    # ── Phase 2 : Vérification de l'espace disque disponible (MANQUANT-03) ──
    if to_copy:
        total_needed = sum(r.source_entry.size for r in to_copy)
        try:
            check_path = _find_existing_ancestor(target_root)
            free_bytes = shutil.disk_usage(str(check_path)).free
            # Alerte si l'espace libre est insuffisant (marge de sécurité 100 Mo)
            if free_bytes < total_needed + 100 * 1024 * 1024:
                report.errors.append((
                    target_root,
                    f"Espace insuffisant sur le disque cible : "
                    f"{total_needed / 1024**3:.2f} Go requis, "
                    f"{free_bytes / 1024**3:.2f} Go disponibles.",
                ))
                report.finished_at = datetime.now()
                return report
        except OSError:
            pass  # Impossible de vérifier — on continue

    # ── Phase 3 : Copie ───────────────────────────────────────────────────────
    for i, result in enumerate(to_copy):
        if cancel_check and cancel_check():
            report.cancelled = True
            break

        filename = str(result.source_entry.relative_path)
        if progress_callback:
            progress_callback(i + 1, total, filename)

        try:
            _atomic_copy(result.source_entry.path, result.target_path)
            report.files_copied.append(result.target_path)
            # OPTIM-02 : accumulation pendant la copie (pas de re-stat)
            report.bytes_copied += result.source_entry.size
        except PermissionError as e:
            report.errors.append((result.source_entry.path, f"Permission refusée : {e}"))
        except OSError as e:
            report.errors.append((result.source_entry.path, str(e)))

    report.finished_at = datetime.now()
    return report
