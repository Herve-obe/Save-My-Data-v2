"""
backup_worker.py — Thread Qt pour exécuter la sauvegarde en arrière-plan.

Le BackupWorker hérite de QThread afin de ne jamais bloquer l'interface
graphique pendant la copie des fichiers.

Organisation sur le disque cible :
    C:\\  ->  <cible>\\[C]\\
    D:\\  ->  <cible>\\[D]\\
    D:\\Photos\\  ->  <cible>\\[Photos]\\
"""

import json
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime

from PySide6.QtCore import QThread, Signal

from .copy_engine import run_backup, CopyReport
from .orphan_manager import OrphanManager
from .path_utils import target_folder_name


# ── Rapport multi-disques ─────────────────────────────────────────────────────

@dataclass
class MultiDiskReport:
    """Agrège les rapports de sauvegarde de tous les disques sources."""
    reports: list[tuple[Path, CopyReport]] = field(default_factory=list)

    @property
    def total_copied(self) -> int:
        return sum(len(r.files_copied) for _, r in self.reports)

    @property
    def total_unchanged(self) -> int:
        return sum(r.files_unchanged for _, r in self.reports)

    @property
    def total_errors(self) -> int:
        return sum(len(r.errors) for _, r in self.reports)

    @property
    def all_orphans(self) -> list[Path]:
        result = []
        for _, r in self.reports:
            result.extend(r.orphan_paths)
        return result

    @property
    def cancelled(self) -> bool:
        return any(r.cancelled for _, r in self.reports)

    def summary(self) -> str:
        return (
            f"Fichiers copiés  : {self.total_copied}\n"
            f"Inchangés        : {self.total_unchanged}\n"
            f"Orphelins        : {len(self.all_orphans)}\n"
            f"Erreurs          : {self.total_errors}"
        )


# ── Worker QThread ────────────────────────────────────────────────────────────

class BackupWorker(QThread):
    """
    Lance la sauvegarde de plusieurs disques sources dans un thread séparé.

    Signaux :
        progress(done, total, filename) — progression fichier par fichier
        disk_started(source_path)       — début de la sauvegarde d'un disque
        finished(MultiDiskReport)       — sauvegarde complète terminée
        error(message)                  — erreur critique non récupérable
    """

    progress    = Signal(int, int, str)   # done, total, fichier courant
    disk_started = Signal(str)            # nom du disque source en cours
    finished    = Signal(object)          # MultiDiskReport
    error       = Signal(str)             # message d'erreur critique

    def __init__(
        self,
        sources: list[Path],
        target: Path,
        filters: dict,
        data_dir: Path,
    ):
        super().__init__()
        self.sources = sources
        self.target = target
        self.filters = filters
        self.data_dir = data_dir
        self._cancel = False

    def cancel(self) -> None:
        """Demande l'annulation propre de la sauvegarde en cours."""
        self._cancel = True

    def run(self) -> None:
        multi = MultiDiskReport()

        for source in self.sources:
            if self._cancel:
                break

            self.disk_started.emit(str(source))
            target_sub = self.target / target_folder_name(source)

            try:
                report = run_backup(
                    source_root=source,
                    target_root=target_sub,
                    excluded_extensions=self.filters.get('excluded_extensions', []),
                    excluded_folders=self.filters.get('excluded_folders', []),
                    max_size_bytes=self.filters.get('max_size_bytes', 0),
                    progress_callback=lambda d, t, f: self.progress.emit(d, t, f),
                    cancel_check=lambda: self._cancel,
                )
                multi.reports.append((source, report))

                # Enregistrer les fichiers orphelins détectés
                if report.orphan_paths:
                    manager = OrphanManager(self.data_dir)
                    manager.add_orphans(report.orphan_paths, source, target_sub)

            except Exception as exc:
                self.error.emit(f"Erreur inattendue sur {source} : {exc}")

        self.finished.emit(multi)


# ── Utilitaires ───────────────────────────────────────────────────────────────

def write_last_backup(data_dir: Path, report: "MultiDiskReport") -> None:
    """
    Persiste les infos de la dernière sauvegarde dans data/last_backup.json.
    Appelé par le dashboard, le scheduler et le menu systray.
    """
    entry = {
        "date":         datetime.now().strftime("%d/%m/%Y à %H:%M"),
        "files_copied": report.total_copied,
        "errors":       report.total_errors,
    }
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / "last_backup.json").write_text(
            json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        pass


