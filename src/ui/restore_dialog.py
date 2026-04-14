"""
restore_dialog.py — Fenêtre de confirmation avant restauration d'un fichier.

Affichée quand l'utilisateur :
  - clique droit → "Restaurer depuis le dernier back-up" dans l'Explorateur
  - clique "Restaurer un fichier..." dans le menu systray

Workflow affiché à l'utilisateur :
  1. Aperçu du fichier sauvegardé (nom, date, taille)
  2. Choix de la destination (emplacement d'origine ou personnalisé)
  3. Avertissement Corbeille
  4. Bouton Restaurer → envoie à la Corbeille + copie depuis sauvegarde
"""

from pathlib import Path
from datetime import datetime

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QFrame, QFileDialog,
    QMessageBox, QProgressBar,
)
from PySide6.QtCore import Qt, Signal, Slot, QThread
from PySide6.QtGui import QFont

from core.restore_engine import RestoreCandidate, restore, RestoreResult


# ── Thread de restauration ────────────────────────────────────────────────────

class RestoreWorker(QThread):
    """Lance la restauration dans un thread séparé (copie potentiellement longue)."""

    finished = Signal(object)  # RestoreResult

    def __init__(self, candidate: RestoreCandidate, destination: Path | None):
        super().__init__()
        self.candidate   = candidate
        self.destination = destination

    def run(self) -> None:
        result = restore(self.candidate, self.destination)
        self.finished.emit(result)


# ── Utilitaire ────────────────────────────────────────────────────────────────

def _fmt_size(size: int) -> str:
    if size < 1024:        return f"{size} o"
    if size < 1024 ** 2:   return f"{size / 1024:.1f} Ko"
    if size < 1024 ** 3:   return f"{size / 1024 ** 2:.1f} Mo"
    return f"{size / 1024 ** 3:.2f} Go"


def _fmt_date(dt: datetime) -> str:
    return dt.strftime("%d/%m/%Y à %H:%M")


# ── Dialogue "Fichier introuvable dans la sauvegarde" ─────────────────────────

class NotFoundDialog(QDialog):
    """Affiché quand le fichier n'a pas de correspondance dans la sauvegarde."""

    def __init__(self, source_path: Path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Save My Data — Fichier introuvable")
        self.setWindowFlags(
            Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setMinimumWidth(420)
        self._build_ui(source_path)

    def _build_ui(self, path: Path) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("Fichier non trouvé dans la sauvegarde")
        font = QFont()
        font.setPointSize(11)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)

        msg = QLabel(
            f"<b>{path.name}</b> n'a pas été trouvé dans votre sauvegarde.\n\n"
            "Ce fichier n'a peut-être jamais été sauvegardé, ou le disque "
            "de sauvegarde n'est pas accessible."
        )
        msg.setWordWrap(True)
        layout.addWidget(msg)

        btn = QPushButton("Fermer")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignRight)


# ── Dialogue principal de confirmation ────────────────────────────────────────

class RestoreDialog(QDialog):
    """
    Fenêtre de confirmation avant restauration.

    Usage :
        candidate = find_backup(path, source_disks, target_disk)
        dialog = RestoreDialog(candidate)
        dialog.exec()
    """

    def __init__(self, candidate: RestoreCandidate, parent=None):
        super().__init__(parent)
        self._candidate  = candidate
        self._destination = None   # None = emplacement d'origine
        self._worker: RestoreWorker | None = None

        self.setWindowTitle("Save My Data — Restaurer")
        self.setWindowFlags(
            Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setMinimumWidth(500)
        self._build_ui()

    # ── Construction ──────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(14)
        root.setContentsMargins(24, 24, 24, 24)

        # Titre
        title = QLabel("Restaurer depuis la sauvegarde ?")
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        title.setFont(font)
        root.addWidget(title)

        # Carte d'information sur le fichier sauvegardé
        root.addWidget(self._build_file_card())

        # Séparateur
        root.addWidget(self._make_sep())

        # Destination
        root.addLayout(self._build_destination_row())

        # Séparateur
        root.addWidget(self._make_sep())

        # Avertissement Corbeille
        warn = QLabel(
            "Le fichier actuel (s'il existe) sera envoyé à la\n"
            "Corbeille avant restauration — vous pourrez l'annuler."
        )
        warn.setStyleSheet("color: #e67e22; font-style: italic;")
        root.addWidget(warn)

        # Barre de progression (cachée au départ)
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)
        root.addWidget(self._progress)

        # Boutons
        root.addLayout(self._build_buttons())

    def _build_file_card(self) -> QFrame:
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QGridLayout(frame)
        layout.setSpacing(6)
        layout.setContentsMargins(14, 14, 14, 14)

        c = self._candidate
        item_type = "Dossier" if c.is_dir else "Fichier"

        rows = [
            (f"{item_type} :", c.source_path.name),
            ("Sauvegardé le :", _fmt_date(c.backup_mtime)),
            ("Taille :", _fmt_size(c.size)),
            ("Emplacement sauvegarde :", str(c.backup_path)),
        ]
        for i, (label, value) in enumerate(rows):
            lbl = QLabel(label)
            lbl.setStyleSheet("color: #666; font-weight: bold;")
            val = QLabel(value)
            val.setWordWrap(True)
            val.setToolTip(value)
            layout.addWidget(lbl, i, 0)
            layout.addWidget(val, i, 1)

        layout.setColumnStretch(1, 1)
        return frame

    def _build_destination_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        lbl = QLabel("Destination :")
        lbl.setStyleSheet("font-weight: bold;")
        row.addWidget(lbl)

        self._dest_label = QLabel(
            f"Emplacement d'origine  ({self._candidate.source_path.parent})"
        )
        self._dest_label.setWordWrap(True)
        row.addWidget(self._dest_label, stretch=1)

        btn_change = QPushButton("Changer...")
        btn_change.clicked.connect(self._pick_destination)
        row.addWidget(btn_change)
        return row

    def _build_buttons(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addStretch()

        self._btn_cancel = QPushButton("Annuler")
        self._btn_cancel.clicked.connect(self.reject)
        row.addWidget(self._btn_cancel)

        self._btn_restore = QPushButton("Restaurer")
        self._btn_restore.setDefault(True)
        self._btn_restore.setMinimumWidth(120)
        self._btn_restore.clicked.connect(self._start_restore)
        row.addWidget(self._btn_restore)
        return row

    def _make_sep(self) -> QFrame:
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        return sep

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _pick_destination(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self,
            "Choisir le dossier de destination",
            str(self._candidate.source_path.parent),
        )
        if folder:
            self._destination = Path(folder)
            self._dest_label.setText(str(self._destination))

    def _start_restore(self) -> None:
        self._btn_restore.setEnabled(False)
        self._btn_cancel.setEnabled(False)
        self._progress.setVisible(True)

        self._worker = RestoreWorker(self._candidate, self._destination)
        self._worker.finished.connect(self._on_restore_done)
        self._worker.start()

    @Slot(object)
    def _on_restore_done(self, result: RestoreResult) -> None:
        self._progress.setVisible(False)
        self._worker = None

        if result.success:
            dst = self._destination or self._candidate.source_path
            detail = f"Restauré dans :\n{dst}"
            if result.sent_to_trash:
                detail += "\n\nL'ancienne version a été envoyée à la Corbeille."
            QMessageBox.information(self, "Restauration réussie", detail)
            self.accept()
        else:
            error_msg = "\n".join(f"• {e}" for _, e in result.errors)
            QMessageBox.critical(
                self, "Échec de la restauration",
                f"La restauration a échoué :\n\n{error_msg}"
            )
            self._btn_restore.setEnabled(True)
            self._btn_cancel.setEnabled(True)

    # ── Empêche fermeture pendant restauration ────────────────────────────────

    def closeEvent(self, event) -> None:
        if self._worker and self._worker.isRunning():
            event.ignore()
        else:
            super().closeEvent(event)
