"""
disk_missing_dialog.py — Alerte quand le disque de sauvegarde est introuvable.

Affiché lors d'une tentative de sauvegarde (extinction ou planifiée)
si le disque cible n'est pas accessible.
"""

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QCloseEvent


class DiskMissingDialog(QDialog):
    """
    Fenêtre d'alerte modale affichée quand le disque cible est absent.

    Résultat accessible via .result() après exec() :
        DiskMissingDialog.CANCEL_SHUTDOWN  → Annuler l'extinction
        DiskMissingDialog.SHUTDOWN_ANYWAY  → Éteindre sans sauvegarde
        DiskMissingDialog.RETRY            → Réessayer (l'utilisateur a branché le disque)
    """

    CANCEL_SHUTDOWN = 0
    SHUTDOWN_ANYWAY = 1
    RETRY           = 2

    def __init__(self, disk_path: Path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Save My Data — Disque introuvable")
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.CustomizeWindowHint
            | Qt.WindowType.WindowTitleHint
        )
        self.setMinimumWidth(460)
        self._chosen = self.CANCEL_SHUTDOWN
        self._setup_ui(disk_path)

    def _setup_ui(self, disk_path: Path) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(28, 28, 28, 28)

        # Titre
        title = QLabel("Disque de sauvegarde introuvable")
        font = QFont()
        font.setPointSize(11)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)

        # Message
        msg = QLabel(
            f"Le disque de sauvegarde <b>{disk_path}</b> n'est pas accessible.\n\n"
            "Branchez le disque et cliquez sur Réessayer, ou choisissez "
            "une autre option."
        )
        msg.setWordWrap(True)
        layout.addWidget(msg)

        layout.addSpacing(8)

        # Bouton 1 — Réessayer (action principale)
        btn_retry = QPushButton("Réessayer  (brancher le disque d'abord)")
        btn_retry.setDefault(True)
        btn_retry.setMinimumHeight(36)
        btn_retry.clicked.connect(lambda: self._choose(self.RETRY))
        layout.addWidget(btn_retry)

        # Bouton 2 — Annuler l'extinction
        btn_cancel = QPushButton("Annuler l'extinction")
        btn_cancel.setMinimumHeight(36)
        btn_cancel.clicked.connect(lambda: self._choose(self.CANCEL_SHUTDOWN))
        layout.addWidget(btn_cancel)

        # Bouton 3 — Éteindre quand même (action risquée, visuellement distincte)
        btn_shutdown = QPushButton("Éteindre sans sauvegarde")
        btn_shutdown.setMinimumHeight(36)
        btn_shutdown.setStyleSheet("color: #c0392b;")
        btn_shutdown.clicked.connect(lambda: self._choose(self.SHUTDOWN_ANYWAY))
        layout.addWidget(btn_shutdown)

    def _choose(self, result: int) -> None:
        self._chosen = result
        self.accept()

    def chosen(self) -> int:
        """Retourne le choix de l'utilisateur après exec()."""
        return self._chosen

    def closeEvent(self, event: QCloseEvent) -> None:
        event.ignore()  # Empêche la fermeture via la croix
