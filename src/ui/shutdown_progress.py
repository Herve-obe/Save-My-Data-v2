"""
shutdown_progress.py — Fenêtre de progression affichée lors de la sauvegarde pré-extinction.

Cette fenêtre reste au premier plan, ne peut pas être fermée manuellement,
et bloque visuellement l'extinction jusqu'à la fin de la sauvegarde.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QProgressBar, QPushButton, QFrame,
)
from PySide6.QtCore import Qt, Signal, Slot, QTimer
from PySide6.QtGui import QFont, QCloseEvent


class ShutdownProgressDialog(QDialog):
    """
    Fenêtre modale affichée pendant la sauvegarde pré-extinction.

    Signaux :
        abort_requested — l'utilisateur a cliqué "Annuler"
    """

    abort_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Save My Data")
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.CustomizeWindowHint
            | Qt.WindowType.WindowTitleHint
        )
        self.setMinimumWidth(540)
        self.setModal(False)
        self._aborted = False
        self._setup_ui()

    # ── Construction de l'interface ───────────────────────────────────────────

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(28, 28, 28, 28)

        # Titre principal
        self._title = QLabel("Sauvegarde en cours avant extinction...")
        font_title = QFont()
        font_title.setPointSize(12)
        font_title.setBold(True)
        self._title.setFont(font_title)
        layout.addWidget(self._title)

        # Disque source en cours
        self._disk_label = QLabel("Analyse des fichiers...")
        layout.addWidget(self._disk_label)

        # Barre de progression (indéterminée au départ)
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setMinimumHeight(22)
        self._progress.setTextVisible(True)
        layout.addWidget(self._progress)

        # Fichier courant (tronqué si trop long)
        self._file_label = QLabel("")
        self._file_label.setWordWrap(False)
        font_small = QFont()
        font_small.setPointSize(9)
        self._file_label.setFont(font_small)
        self._file_label.setStyleSheet("color: #666;")
        layout.addWidget(self._file_label)

        # Compteur de fichiers
        self._stats_label = QLabel("Préparation...")
        layout.addWidget(self._stats_label)

        # Séparateur
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep)

        # Bouton annuler
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._btn_cancel = QPushButton("Annuler la sauvegarde et éteindre")
        self._btn_cancel.setMinimumWidth(240)
        self._btn_cancel.clicked.connect(self._on_cancel_clicked)
        btn_row.addWidget(self._btn_cancel)
        layout.addLayout(btn_row)

    # ── Slots de mise à jour ──────────────────────────────────────────────────

    @Slot(str)
    def on_disk_started(self, disk_path: str) -> None:
        """Appelé quand la sauvegarde d'un nouveau disque source commence."""
        self._disk_label.setText(f"Disque source : {disk_path}")

    @Slot(int, int, str)
    def on_progress(self, done: int, total: int, filename: str) -> None:
        """Appelé à chaque fichier traité par le BackupWorker."""
        if total > 0:
            self._progress.setRange(0, total)
            self._progress.setValue(done)
            self._stats_label.setText(
                f"{done} / {total} fichier(s) traité(s)"
            )
        # Tronquer le nom de fichier pour qu'il tienne sur une ligne
        short = filename[-70:] if len(filename) > 70 else filename
        self._file_label.setText(short)

    def on_finished(self, copied: int, errors: int) -> None:
        """Appelé quand la sauvegarde est terminée avec succès."""
        self._progress.setRange(0, 1)
        self._progress.setValue(1)
        self._title.setText("Sauvegarde terminée. Extinction en cours...")
        self._disk_label.setText("")
        self._file_label.setText("")
        self._stats_label.setText(
            f"{copied} fichier(s) copié(s)"
            + (f" — {errors} erreur(s)" if errors else "")
        )
        self._btn_cancel.setEnabled(False)

    # ── Annulation ────────────────────────────────────────────────────────────

    def _on_cancel_clicked(self) -> None:
        if self._aborted:
            return
        self._aborted = True
        self._btn_cancel.setEnabled(False)
        self._title.setText("Annulation en cours...")
        self._disk_label.setText("La sauvegarde sera interrompue.")
        self.abort_requested.emit()

    # ── Empêche la fermeture manuelle ─────────────────────────────────────────

    def closeEvent(self, event: QCloseEvent) -> None:
        event.ignore()
