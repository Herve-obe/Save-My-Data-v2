"""
backup_worker.py — Thread Qt pour exécuter la sauvegarde en arrière-plan.

Le BackupWorker hérite de QThread afin de ne jamais bloquer l'interface
graphique pendant la copie des fichiers.

Organisation sur le disque cible :
    C:\\  ->  <cible>\\[C]\\
    D:\\  ->  <cible>\\[D]\\
    D:\\Photos\\  ->  <cible>\\[D_Photos]\\
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
    def total_bytes_copied(self) -> int:
        return sum(r.bytes_copied for _, r in self.reports)

    @property
    def total_duration_seconds(self) -> float:
        return sum(r.duration_seconds for _, r in self.reports)

    @property
    def all_orphans(self) -> list[Path]:
        result = []
        for _, r in self.reports:
            result.extend(r.orphan_paths)
        return result

    @property
    def cancelled(self) -> bool:
        return any(r.cancelled for _, r in self.reports)

    @property
    def sources(self) -> list[Path]:
        """Retourne la liste des disques sources traités."""
        return [src for src, _ in self.reports]

    def summary(self) -> str:
        return (
            f"Fichiers copiés  : {self.total_copied}\n"
            f"Inchangés        : {self.total_unchanged}\n"
            f"Orphelins        : {len(self.all_orphans)}\n"
            f"Erreurs          : {self.total_errors}"
        )


# ── Nettoyage des résidus de crash ────────────────────────────────────────────

def clean_tmp_files(target_root: Path) -> int:
    """
    Supprime les fichiers .smd_tmp résiduels du dossier cible.

    Ces fichiers sont créés par l'écriture atomique et normalement renommés
    immédiatement. S'ils subsistent, c'est le signe d'un crash en cours de copie.

    Returns:
        Nombre de fichiers temporaires supprimés.
    """
    count = 0
    if not target_root.exists():
        return 0
    try:
        for tmp_file in target_root.rglob("*.smd_tmp"):
            try:
                tmp_file.unlink(missing_ok=True)
                count += 1
            except OSError:
                pass
    except OSError:
        pass
    return count


# ── Worker QThread ────────────────────────────────────────────────────────────

class BackupWorker(QThread):
    """
    Lance la sauvegarde de plusieurs disques sources dans un thread séparé.

    Signaux :
        progress(done, total, filename) — progression fichier par fichier
        disk_started(source_path)       — début de la sauvegarde d'un disque
        finished(MultiDiskReport)       — sauvegarde complète terminée
        error(message)                  — erreur critique non récupérable
        low_disk_warning(disk, pct_free)— espace disque cible < 10 %
    """

    progress         = Signal(int, int, str)   # done, total, fichier courant
    disk_started     = Signal(str)             # nom du disque source en cours
    finished         = Signal(object)          # MultiDiskReport
    error            = Signal(str)             # message d'erreur critique
    low_disk_warning = Signal(str, int)        # (chemin_cible, % libre) — MANQUANT-02

    def __init__(
        self,
        sources: list[Path],
        target: Path,
        filters: dict,
        data_dir: Path,
    ):
        super().__init__()
        self.sources  = sources
        self.target   = target
        self.filters  = filters
        self.data_dir = data_dir
        self._cancel  = False

    def cancel(self) -> None:
        """Demande l'annulation propre de la sauvegarde en cours."""
        self._cancel = True

    # ── Méthodes internes (remplacent les lambdas — BUG-04) ──────────────────

    def _emit_progress(self, done: int, total: int, filename: str) -> None:
        self.progress.emit(done, total, filename)

    def _is_cancelled(self) -> bool:
        return self._cancel

    # ── Thread principal ──────────────────────────────────────────────────────

    def run(self) -> None:
        multi = MultiDiskReport()

        for source in self.sources:
            if self._cancel:
                break

            self.disk_started.emit(str(source))
            target_sub = self.target / target_folder_name(source)

            # MANQUANT-04 : nettoyer les .smd_tmp résiduels avant la sauvegarde
            clean_tmp_files(target_sub)

            try:
                report = run_backup(
                    source_root=source,
                    target_root=target_sub,
                    excluded_extensions=self.filters.get("excluded_extensions", []),
                    excluded_folders=self.filters.get("excluded_folders", []),
                    max_size_bytes=self.filters.get("max_size_bytes", 0),
                    progress_callback=self._emit_progress,
                    cancel_check=self._is_cancelled,
                )
                multi.reports.append((source, report))

                # Enregistrer les fichiers orphelins détectés
                if report.orphan_paths:
                    manager = OrphanManager(self.data_dir)
                    manager.add_orphans(report.orphan_paths, source, target_sub)

                # MANQUANT-02 : alerte si espace cible < 10 %
                self._check_disk_space_warning()

            except Exception as exc:
                self.error.emit(f"Erreur inattendue sur {source} : {exc}")

        self.finished.emit(multi)

    def _check_disk_space_warning(self) -> None:
        """Émet low_disk_warning si le disque cible a < 10 % d'espace libre."""
        try:
            import psutil
            usage = psutil.disk_usage(str(self.target))
            pct_free = 100 - int(usage.percent)
            if pct_free < 10:
                self.low_disk_warning.emit(str(self.target), pct_free)
        except Exception:
            pass


# ── Utilitaires de persistance ────────────────────────────────────────────────

def write_last_backup(data_dir: Path, report: "MultiDiskReport") -> None:
    """
    Persiste les infos de la dernière sauvegarde dans data/last_backup.json
    ET ajoute une entrée dans data/backup_history.jsonl.

    Appelé par le dashboard, le scheduler et le menu systray.
    MANQUANT-05 : inclut maintenant la durée et les fichiers inchangés.
    """
    entry = {
        "date":             datetime.now().strftime("%d/%m/%Y à %H:%M"),
        "files_copied":     report.total_copied,
        "files_unchanged":  report.total_unchanged,
        "errors":           report.total_errors,
        "duration_s":       round(report.total_duration_seconds, 1),
    }
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / "last_backup.json").write_text(
            json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        pass

    # Appendre au journal complet d'historique
    _append_backup_history(data_dir, entry, report)


def _append_backup_history(
    data_dir: Path,
    entry: dict,
    report: "MultiDiskReport",
) -> None:
    """
    Ajoute une ligne au fichier backup_history.jsonl (format JSON Lines).
    Chaque ligne est un objet JSON autonome horodaté.
    """
    history_entry = dict(entry)
    history_entry["sources"] = [str(s) for s in report.sources]

    try:
        history_path = data_dir / "backup_history.jsonl"
        with open(history_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(history_entry, ensure_ascii=False) + "\n")
    except Exception:
        pass
