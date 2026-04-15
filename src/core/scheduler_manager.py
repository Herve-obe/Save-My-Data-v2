"""
scheduler_manager.py — Planificateur de sauvegardes à heure fixe.

Utilise APScheduler (BackgroundScheduler) dans un thread séparé.
Un objet bridge QObject permet de transférer le déclenchement vers le
thread Qt principal (via QueuedConnection) pour créer le BackupWorker
en toute sécurité.

Cycle de vie :
    scheduler = SchedulerManager(tray, data_dir)
    scheduler.start()          # appelé dans launch_gui()
    scheduler.reschedule()     # appelé après chaque changement de config
    scheduler.stop()           # appelé sur app.aboutToQuit
"""

from pathlib import Path

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QSystemTrayIcon

import config


# ── Bridge thread-safe ────────────────────────────────────────────────────────

class _Bridge(QObject):
    """
    Relie le thread APScheduler au thread Qt principal.

    APScheduler appelle `triggered.emit()` depuis un thread worker ;
    Qt délivre le signal en QueuedConnection dans le thread principal
    (car _Bridge est créé dans le thread principal).
    """
    triggered = Signal()


# ── Manager ───────────────────────────────────────────────────────────────────

class SchedulerManager:
    """
    Gère le job de sauvegarde planifiée.

    Paramètres lus depuis config :
        backup.mode            — 'shutdown' | 'scheduled' | 'both'
        backup.scheduled_time  — 'HH:MM'
    """

    def __init__(self, tray: QSystemTrayIcon | None, data_dir: Path):
        self._tray      = tray
        self._data_dir  = data_dir
        self._scheduler = None
        self._worker    = None          # garde une référence au worker actif

        # Le bridge est créé ici, dans le thread Qt principal
        self._bridge = _Bridge()
        self._bridge.triggered.connect(self._run_scheduled_backup)

    # ── Cycle de vie ──────────────────────────────────────────────────────────

    def start(self) -> None:
        """Démarre le BackgroundScheduler et planifie le job selon la config."""
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
        except ImportError:
            return

        self._scheduler = BackgroundScheduler(
            job_defaults={"misfire_grace_time": 300},  # 5 min de tolérance
        )
        self._scheduler.start()
        self._update_job()

    def reschedule(self) -> None:
        """Relit la config et met à jour le job (appelé après sauvegarde des paramètres)."""
        if self._scheduler is None or not self._scheduler.running:
            return
        self._update_job()

    def stop(self) -> None:
        """Arrête proprement le scheduler (appelé sur app.aboutToQuit)."""
        if self._scheduler and self._scheduler.running:
            try:
                self._scheduler.shutdown(wait=False)
            except Exception:
                pass

    # ── Gestion du job ────────────────────────────────────────────────────────

    def _update_job(self) -> None:
        """Ajoute, modifie ou supprime le job cron selon la config courante."""
        cfg  = config.reload()
        mode = cfg.get("backup", {}).get("mode", "shutdown")
        time_str = cfg.get("backup", {}).get("scheduled_time", "22:00")

        # Supprimer l'éventuel job existant
        if self._scheduler.get_job("scheduled_backup"):
            self._scheduler.remove_job("scheduled_backup")

        if mode not in ("scheduled", "both"):
            return  # Pas de sauvegarde planifiée à ajouter

        # Parsing de l'heure
        try:
            parts  = time_str.split(":")
            hour   = int(parts[0])
            minute = int(parts[1]) if len(parts) > 1 else 0
        except (ValueError, IndexError):
            hour, minute = 22, 0

        self._scheduler.add_job(
            self._bridge.triggered.emit,
            trigger="cron",
            hour=hour,
            minute=minute,
            id="scheduled_backup",
            replace_existing=True,
        )

    # ── Exécution (thread Qt principal) ──────────────────────────────────────

    def _run_scheduled_backup(self) -> None:
        """
        Lancé dans le thread Qt principal via le bridge.
        Crée et démarre un BackupWorker, notifie via le systray.
        """
        from core.backup_worker import BackupWorker

        # Guard : ignorer si une sauvegarde planifiée est déjà en cours
        # (ex. déclenchement double après veille prolongée ou correction d'horloge)
        if self._worker is not None and self._worker.isRunning():
            return

        cfg         = config.reload()
        target_str  = cfg.get("backup", {}).get("target_disk", "")
        source_strs = cfg.get("backup", {}).get("source_disks", [])
        filters     = cfg.get("filters", {})

        if not target_str or not source_strs:
            return

        target  = Path(target_str)
        sources = [Path(s) for s in source_strs]

        self._notify(
            "Sauvegarde planifiée en cours…",
            QSystemTrayIcon.MessageIcon.Information,
            2000,
        )

        worker = BackupWorker(sources, target, filters, self._data_dir)
        worker.finished.connect(self._on_backup_done)
        worker.error.connect(self._on_backup_error)
        worker.start()

        # Garder une référence pour éviter le garbage collection
        self._worker = worker

    def _on_backup_error(self, message: str) -> None:
        """Appelé si le BackupWorker émet une erreur critique (ex. disque inaccessible)."""
        self._notify(
            f"Erreur lors de la sauvegarde planifiée :\n{message}",
            QSystemTrayIcon.MessageIcon.Warning,
            8000,
        )

    def _on_backup_done(self, report) -> None:
        """Appelé dans le thread Qt principal quand la sauvegarde planifiée est finie."""
        n_copied  = report.total_copied
        n_errors  = report.total_errors
        n_orphans = len(report.all_orphans)

        if report.cancelled:
            self._worker = None   # Libère la référence même en cas d'annulation
            return

        from core.backup_worker import write_last_backup
        write_last_backup(self._data_dir, report)

        lines = [f"Sauvegarde planifiée terminée — {n_copied} fichier(s) copié(s)."]
        if n_errors:
            lines.append(f"{n_errors} erreur(s).")
        if n_orphans:
            lines.append(f"{n_orphans} orphelin(s) à réviser.")

        self._notify(
            "\n".join(lines),
            QSystemTrayIcon.MessageIcon.Information,
            6000,
        )

        self._worker = None

    # ── Utilitaire ────────────────────────────────────────────────────────────

    def _notify(self, message: str, icon, duration_ms: int) -> None:
        if self._tray:
            self._tray.showMessage("Save My Data", message, icon, duration_ms)
