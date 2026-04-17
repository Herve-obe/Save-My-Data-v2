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

import json
from datetime import datetime, timedelta
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
        self._catchup_pending = False   # True si le prochain déclenchement est un rattrapage

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
        self._schedule_catchup_if_needed()

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

    # ── Rattrapage au démarrage ───────────────────────────────────────────────

    def _schedule_catchup_if_needed(self) -> None:
        """
        Déclenche une sauvegarde de rattrapage si la sauvegarde planifiée du
        jour a été manquée (ordinateur éteint à l'heure prévue).

        Conditions pour déclencher le rattrapage :
          1. Mode = 'scheduled' ou 'both'
          2. L'heure planifiée d'aujourd'hui est déjà passée
          3. Aucune sauvegarde n'a eu lieu aujourd'hui
        """
        if self._scheduler is None or not self._scheduler.running:
            return

        cfg = config.reload()
        mode = cfg.get("backup", {}).get("mode", "shutdown")
        if mode not in ("scheduled", "both"):
            return

        time_str = cfg.get("backup", {}).get("scheduled_time", "22:00")
        try:
            parts  = time_str.split(":")
            hour   = int(parts[0])
            minute = int(parts[1]) if len(parts) > 1 else 0
        except (ValueError, IndexError):
            return

        now = datetime.now()
        scheduled_today = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

        # L'heure planifiée n'est pas encore passée aujourd'hui → rien à rattraper
        if now < scheduled_today:
            return

        # Une sauvegarde a déjà eu lieu aujourd'hui → pas de rattrapage
        last = self._last_backup_date()
        if last is not None and last.date() >= now.date():
            return

        # Planifier le rattrapage 15 secondes après le démarrage
        self._catchup_pending = True
        self._scheduler.add_job(
            self._bridge.triggered.emit,
            trigger="date",
            run_date=now + timedelta(seconds=15),
            id="catchup_backup",
            replace_existing=True,
        )

    def _last_backup_date(self) -> "datetime | None":
        """Lit la date de la dernière sauvegarde depuis last_backup.json."""
        p = self._data_dir / "last_backup.json"
        if not p.exists():
            return None
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            date_str = data.get("date", "")  # format : "dd/MM/yyyy à HH:mm"
            if date_str:
                return datetime.strptime(date_str, "%d/%m/%Y à %H:%M")
        except Exception:
            pass
        return None

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

        is_catchup = self._catchup_pending
        self._catchup_pending = False
        msg = ("Sauvegarde de rattrapage en cours… (heure planifiée manquée)"
               if is_catchup else "Sauvegarde planifiée en cours…")
        self._notify(msg, QSystemTrayIcon.MessageIcon.Information, 2000)

        worker = BackupWorker(sources, target, filters, self._data_dir)
        worker.finished.connect(self._on_backup_done)
        worker.error.connect(self._on_backup_error)
        worker.low_disk_warning.connect(self._on_low_disk_warning)
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

    def _on_low_disk_warning(self, disk: str, pct_free: int) -> None:
        """Notifie si l'espace disque cible est faible (< 10 %)."""
        self._notify(
            f"Espace disque faible sur la cible ({pct_free}% libre) :\n{disk}",
            QSystemTrayIcon.MessageIcon.Warning,
            6000,
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
