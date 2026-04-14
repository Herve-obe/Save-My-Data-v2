"""
restore_page.py — Page de restauration de fichiers depuis la sauvegarde.
"""

from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QFileDialog, QMessageBox,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

import config
from core.restore_engine import find_backup
from ui.restore_dialog import RestoreDialog, NotFoundDialog


class RestorePage(QWidget):
    """Page de restauration de fichiers."""

    def __init__(self, data_dir: Path, parent=None):
        super().__init__(parent)
        self._data_dir = data_dir
        self._build_ui()

    # ── Construction ──────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 36, 36, 36)
        layout.setSpacing(20)

        # Titre
        title = QLabel("Restaurer un fichier")
        f = QFont()
        f.setPointSize(15)
        f.setBold(True)
        title.setFont(f)
        layout.addWidget(title)

        desc = QLabel(
            "Choisissez un fichier ou un dossier à restaurer depuis votre sauvegarde.\n"
            "Le fichier actuel sera d'abord envoyé à la Corbeille (récupérable)."
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep)

        # ── Choisir un fichier ────────────────────────────────────────────────
        card_file = QFrame()
        card_file.setFrameShape(QFrame.Shape.StyledPanel)
        card_layout = QVBoxLayout(card_file)
        card_layout.setContentsMargins(20, 16, 20, 16)
        card_layout.setSpacing(10)

        lbl_file = QLabel("Restaurer un fichier spécifique")
        lbl_file_f = QFont()
        lbl_file_f.setBold(True)
        lbl_file.setFont(lbl_file_f)
        card_layout.addWidget(lbl_file)

        lbl_file_desc = QLabel(
            "Naviguez jusqu'au fichier dont vous souhaitez récupérer "
            "la version sauvegardée."
        )
        lbl_file_desc.setWordWrap(True)
        card_layout.addWidget(lbl_file_desc)

        row_file = QHBoxLayout()
        btn_file = QPushButton("Choisir un fichier...")
        btn_file.setMinimumWidth(180)
        btn_file.clicked.connect(self._pick_file)
        row_file.addWidget(btn_file)
        row_file.addStretch()
        card_layout.addLayout(row_file)

        layout.addWidget(card_file)

        # ── Choisir un dossier ────────────────────────────────────────────────
        card_folder = QFrame()
        card_folder.setFrameShape(QFrame.Shape.StyledPanel)
        cf_layout = QVBoxLayout(card_folder)
        cf_layout.setContentsMargins(20, 16, 20, 16)
        cf_layout.setSpacing(10)

        lbl_folder = QLabel("Restaurer un dossier entier")
        lbl_folder_f = QFont()
        lbl_folder_f.setBold(True)
        lbl_folder.setFont(lbl_folder_f)
        cf_layout.addWidget(lbl_folder)

        lbl_folder_desc = QLabel(
            "Restaure l'ensemble du dossier depuis la sauvegarde. "
            "Le dossier actuel sera d'abord envoyé à la Corbeille."
        )
        lbl_folder_desc.setWordWrap(True)
        cf_layout.addWidget(lbl_folder_desc)

        row_folder = QHBoxLayout()
        btn_folder = QPushButton("Choisir un dossier...")
        btn_folder.setMinimumWidth(180)
        btn_folder.clicked.connect(self._pick_folder)
        row_folder.addWidget(btn_folder)
        row_folder.addStretch()
        cf_layout.addLayout(row_folder)

        layout.addWidget(card_folder)

        # ── Astuce clic droit ─────────────────────────────────────────────────
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep2)

        tip = QLabel(
            "Astuce : Si le clic droit est activé dans les Paramètres, vous pouvez "
            "aussi faire un clic droit sur n'importe quel fichier dans l'Explorateur "
            "Windows et choisir « Restaurer depuis le dernier back-up »."
        )
        tip.setWordWrap(True)
        layout.addWidget(tip)

        layout.addStretch()

    # ── Actions ───────────────────────────────────────────────────────────────

    def _pick_file(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(
            self, "Sélectionner un fichier à restaurer"
        )
        if path_str:
            self._restore(Path(path_str))

    def _pick_folder(self) -> None:
        path_str = QFileDialog.getExistingDirectory(
            self, "Sélectionner un dossier à restaurer"
        )
        if path_str:
            self._restore(Path(path_str))

    def _restore(self, source_path: Path) -> None:
        cfg = config.load()
        target_str  = cfg.get("backup", {}).get("target_disk", "")
        source_strs = cfg.get("backup", {}).get("source_disks", [])

        if not target_str or not source_strs:
            QMessageBox.warning(
                self, "Save My Data",
                "Aucun disque de sauvegarde configuré.\n"
                "Allez dans « Mes disques » pour configurer votre sauvegarde."
            )
            return

        source_disks = [Path(s) for s in source_strs]
        target_disk  = Path(target_str)

        candidate = find_backup(source_path, source_disks, target_disk)
        if candidate is None:
            NotFoundDialog(source_path, self).exec()
        else:
            RestoreDialog(candidate, self).exec()
