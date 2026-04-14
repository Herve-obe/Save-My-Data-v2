"""
history_page.py — Page d'historique des sauvegardes.

M5 : affiche la dernière sauvegarde depuis data/last_backup.json.
M6+ : historique complet avec journal d'événements.
"""

import json
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QFrame, QGridLayout,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont


class HistoryPage(QWidget):
    """Page historique des sauvegardes."""

    def __init__(self, data_dir: Path, parent=None):
        super().__init__(parent)
        self._data_dir = data_dir
        self._build_ui()

    # ── Construction ──────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 36, 36, 36)
        layout.setSpacing(16)

        # Titre
        title = QLabel("Historique")
        f = QFont()
        f.setPointSize(15)
        f.setBold(True)
        title.setFont(f)
        layout.addWidget(title)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep)

        # Carte dernière sauvegarde
        self._card = QFrame()
        self._card.setFrameShape(QFrame.Shape.StyledPanel)
        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(20, 16, 20, 16)
        card_layout.setSpacing(10)

        lbl_title = QLabel("Dernière sauvegarde")
        lbl_f = QFont()
        lbl_f.setBold(True)
        lbl_f.setPointSize(11)
        lbl_title.setFont(lbl_f)
        card_layout.addWidget(lbl_title)

        self._grid_layout = QGridLayout()
        self._grid_layout.setSpacing(6)
        card_layout.addLayout(self._grid_layout)

        layout.addWidget(self._card)

        # Note M6
        note = QLabel(
            "L'historique complet avec le journal détaillé de chaque "
            "sauvegarde sera disponible dans une prochaine version."
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        layout.addStretch()

        self.refresh()

    # ── Refresh ───────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        # Vider la grille
        while self._grid_layout.count():
            child = self._grid_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        last = self._load_last_backup()

        if last is None:
            self._card.setVisible(False)
            return

        self._card.setVisible(True)

        rows = [
            ("Date",            last.get("date", "—")),
            ("Fichiers copiés", str(last.get("files_copied", 0))),
            ("Erreurs",         str(last.get("errors", 0))),
        ]

        for i, (label, value) in enumerate(rows):
            lbl = QLabel(f"{label} :")
            lbl.setStyleSheet("font-weight: bold;")
            val = QLabel(value)
            self._grid_layout.addWidget(lbl, i, 0)
            self._grid_layout.addWidget(val, i, 1)

        self._grid_layout.setColumnStretch(1, 1)

    # ── Chargement ────────────────────────────────────────────────────────────

    def _load_last_backup(self) -> dict | None:
        p = self._data_dir / "last_backup.json"
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                pass
        return None
