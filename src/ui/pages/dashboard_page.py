"""
dashboard_page.py — Page d'accueil : statut, disques configurés, sauvegarde.
"""

from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QProgressBar, QScrollArea,
    QMessageBox,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

import config
from core.orphan_manager import OrphanManager
from core.backup_worker import write_last_backup
from ui.utils import load_last_backup


class DashboardPage(QWidget):
    """Page tableau de bord."""

    def __init__(self, data_dir: Path, tray=None, parent=None):
        super().__init__(parent)
        self._data_dir = data_dir
        self._tray = tray
        self._worker = None
        self._build_ui()

    # ── Construction ──────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(36, 36, 36, 36)
        layout.setSpacing(20)

        # Titre
        title = QLabel("Tableau de bord")
        f = QFont()
        f.setPointSize(15)
        f.setBold(True)
        title.setFont(f)
        layout.addWidget(title)

        # Carte de statut
        self._status_card = self._make_status_card()
        layout.addWidget(self._status_card)

        # Bandeau orphelins (masqué par défaut)
        self._orphan_banner = self._make_orphan_banner()
        layout.addWidget(self._orphan_banner)

        # Section disques
        disk_title = QLabel("Disques configurés")
        f2 = QFont()
        f2.setPointSize(11)
        f2.setBold(True)
        disk_title.setFont(f2)
        layout.addWidget(disk_title)

        self._disk_list_layout = QVBoxLayout()
        self._disk_list_layout.setSpacing(8)
        layout.addLayout(self._disk_list_layout)

        # Bouton sauvegarde
        layout.addSpacing(8)
        btn_row = QHBoxLayout()
        self._btn_backup = QPushButton("Lancer une sauvegarde maintenant")
        self._btn_backup.setFixedHeight(44)
        self._btn_backup.setStyleSheet(
            "QPushButton { background: #3b82f6; color: white; border: none; "
            "border-radius: 8px; font-size: 14px; font-weight: bold; padding: 0 20px; }"
            "QPushButton:hover { background: #2563eb; }"
            "QPushButton:disabled { background: #374151; color: #6b7280; }"
        )
        self._btn_backup.clicked.connect(self._start_backup)
        btn_row.addWidget(self._btn_backup)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._progress_label = QLabel("")
        self._progress_label.setVisible(False)
        layout.addWidget(self._progress_label)

        layout.addStretch()

        wrapper = QVBoxLayout(self)
        wrapper.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(content)
        wrapper.addWidget(scroll)

        # Charger les données réelles dès l'ouverture
        self.refresh()

    def _make_status_card(self) -> QFrame:
        card = QFrame()
        card.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(6)

        row = QHBoxLayout()
        self._status_dot = QLabel("●")
        self._status_dot.setStyleSheet("color: #22c55e; font-size: 20px;")
        row.addWidget(self._status_dot)

        self._status_label = QLabel("Actif — prêt à sauvegarder")
        f = QFont()
        f.setPointSize(12)
        f.setBold(True)
        self._status_label.setFont(f)
        row.addWidget(self._status_label)
        row.addStretch()
        layout.addLayout(row)

        self._last_backup_label = QLabel("Aucune sauvegarde enregistrée.")
        layout.addWidget(self._last_backup_label)

        self._mode_label = QLabel("")
        layout.addWidget(self._mode_label)

        return card

    def _make_orphan_banner(self) -> QFrame:
        banner = QFrame()
        banner.setFrameShape(QFrame.Shape.StyledPanel)
        banner.setStyleSheet(
            "QFrame { background: #431407; border: 1px solid #c2410c; border-radius: 8px; }"
        )
        layout = QHBoxLayout(banner)
        layout.setContentsMargins(16, 10, 16, 10)

        self._orphan_label = QLabel("")
        self._orphan_label.setStyleSheet("color: #fed7aa; font-weight: bold;")
        layout.addWidget(self._orphan_label)
        layout.addStretch()

        btn = QPushButton("Réviser")
        btn.setStyleSheet(
            "QPushButton { background: #ea580c; color: white; border: none; "
            "border-radius: 6px; padding: 4px 16px; }"
            "QPushButton:hover { background: #c2410c; }"
        )
        btn.clicked.connect(self._open_orphans)
        layout.addWidget(btn)

        banner.setVisible(False)
        return banner

    # ── Refresh ───────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        """Met à jour l'affichage avec les données actuelles."""
        cfg = config.load()
        self._refresh_status(cfg)
        self._refresh_orphans()
        self._refresh_disks(cfg)

    def _refresh_status(self, cfg: dict) -> None:
        target  = cfg.get("backup", {}).get("target_disk", "")
        sources = cfg.get("backup", {}).get("source_disks", [])
        mode    = cfg.get("backup", {}).get("mode", "shutdown")

        if not target or not sources:
            self._status_dot.setStyleSheet("color: #f59e0b; font-size: 20px;")
            self._status_label.setText("Configuration incomplète")
            self._mode_label.setText("Aucun disque configuré — allez dans « Mes disques ».")
            self._last_backup_label.setText("")
            return

        self._status_dot.setStyleSheet("color: #22c55e; font-size: 20px;")
        self._status_label.setText("Actif — prêt à sauvegarder")

        mode_texts = {
            "shutdown":  "Sauvegarde automatique à l'extinction",
            "scheduled": "Sauvegarde planifiée",
            "both":      "Sauvegarde à l'extinction + planifiée",
        }
        self._mode_label.setText(mode_texts.get(mode, ""))

        last = self._load_last_backup()
        if last:
            self._last_backup_label.setText(
                f"Dernière sauvegarde : {last.get('date', '?')} — "
                f"{last.get('files_copied', 0)} fichier(s) copié(s)"
                + (f", {last.get('errors', 0)} erreur(s)" if last.get("errors") else "")
            )
        else:
            self._last_backup_label.setText("Aucune sauvegarde enregistrée.")

    def _refresh_orphans(self) -> None:
        manager = OrphanManager(self._data_dir)
        n = manager.count_pending()
        if n > 0:
            s = "s" if n > 1 else ""
            self._orphan_label.setText(f"{n} fichier{s} orphelin{s} à réviser")
            self._orphan_banner.setVisible(True)
        else:
            self._orphan_banner.setVisible(False)

    def _refresh_disks(self, cfg: dict) -> None:
        try:
            import psutil
            _has_psutil = True
        except ImportError:
            _has_psutil = False

        # Vider la liste
        while self._disk_list_layout.count():
            child = self._disk_list_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        target  = cfg.get("backup", {}).get("target_disk", "")
        sources = cfg.get("backup", {}).get("source_disks", [])

        if not target and not sources:
            lbl = QLabel("Aucun disque configuré. Allez dans « Mes disques ».")
            self._disk_list_layout.addWidget(lbl)
            return

        all_paths = list(dict.fromkeys(sources + ([target] if target else [])))

        for path_str in all_paths:
            role = "Cible" if path_str == target else "Source"
            p = Path(path_str)

            row = QFrame()
            row.setFrameShape(QFrame.Shape.StyledPanel)
            row_layout = QVBoxLayout(row)
            row_layout.setContentsMargins(14, 10, 14, 10)
            row_layout.setSpacing(4)

            label_row = QHBoxLayout()
            lbl_name = QLabel(f"{path_str}  [{role}]")
            f = QFont()
            f.setBold(True)
            lbl_name.setFont(f)
            label_row.addWidget(lbl_name)
            label_row.addStretch()

            if _has_psutil:
                try:
                    usage = psutil.disk_usage(str(p))
                    free_gb  = usage.free  / 1024**3
                    total_gb = usage.total / 1024**3
                    pct = int(usage.percent)

                    lbl_free = QLabel(f"{free_gb:.1f} Go libres / {total_gb:.0f} Go")
                    label_row.addWidget(lbl_free)
                    row_layout.addLayout(label_row)

                    bar = QProgressBar()
                    bar.setRange(0, 100)
                    bar.setValue(pct)
                    bar.setTextVisible(False)
                    bar.setFixedHeight(8)
                    if pct > 85:
                        bar.setStyleSheet(
                            "QProgressBar { background: transparent; border: none; border-radius: 4px; }"
                            "QProgressBar::chunk { background: #ef4444; border-radius: 4px; }"
                        )
                    row_layout.addWidget(bar)

                except (OSError, FileNotFoundError):
                    lbl_err = QLabel("Inaccessible")
                    lbl_err.setStyleSheet("color: #f59e0b;")
                    label_row.addWidget(lbl_err)
                    row_layout.addLayout(label_row)
            else:
                row_layout.addLayout(label_row)

            self._disk_list_layout.addWidget(row)

    def _load_last_backup(self) -> dict | None:
        return load_last_backup(self._data_dir)

    # ── Actions ───────────────────────────────────────────────────────────────

    def _start_backup(self) -> None:
        from core.backup_worker import BackupWorker

        cfg = config.load()
        target_str  = cfg.get("backup", {}).get("target_disk", "")
        source_strs = cfg.get("backup", {}).get("source_disks", [])
        filters     = cfg.get("filters", {})

        if not target_str or not source_strs:
            QMessageBox.warning(
                self, "Save My Data",
                "Aucun disque configuré. Allez dans « Mes disques »."
            )
            return

        self._btn_backup.setEnabled(False)
        self._btn_backup.setText("Sauvegarde en cours...")
        self._progress_label.setText("Démarrage...")
        self._progress_label.setVisible(True)

        sources = [Path(s) for s in source_strs]
        target  = Path(target_str)

        self._worker = BackupWorker(sources, target, filters, self._data_dir)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_backup_done)
        self._worker.error.connect(
            lambda msg: self._progress_label.setText(f"Erreur : {msg}")
        )
        self._worker.low_disk_warning.connect(self._on_low_disk_warning)
        self._worker.start()

    def _on_low_disk_warning(self, disk: str, pct_free: int) -> None:
        QMessageBox.warning(
            self, "Espace disque faible",
            f"Le disque cible est presque plein ({pct_free}% libre) :\n{disk}"
        )

    def _on_progress(self, done: int, total: int, filename: str) -> None:
        if total > 0:
            name = Path(filename).name if filename else ""
            self._progress_label.setText(f"{done} / {total} — {name}")

    def _on_backup_done(self, report) -> None:
        # Enregistrer les infos de la dernière sauvegarde
        write_last_backup(self._data_dir, report)

        self._btn_backup.setEnabled(True)
        self._btn_backup.setText("Lancer une sauvegarde maintenant")
        self._progress_label.setVisible(False)
        self._worker = None

        msg = f"Sauvegarde terminée — {report.total_copied} fichier(s) copié(s)."
        if report.total_errors:
            msg += f"\n{report.total_errors} erreur(s)."

        QMessageBox.information(self, "Sauvegarde terminée", msg)
        self.refresh()

    def _open_orphans(self) -> None:
        from ui.orphan_review_dialog import OrphanReviewDialog

        manager = OrphanManager(self._data_dir)
        pending = manager.pending
        if pending:
            dialog = OrphanReviewDialog(pending, self._data_dir, self)
            dialog.exec()
            self.refresh()
