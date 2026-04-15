"""
history_page.py — Page d'historique des sauvegardes.

Affiche l'historique complet depuis data/backup_history.jsonl
(une entrée JSON par ligne, les plus récentes en tête).
"""

import json
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QScrollArea, QPushButton, QMessageBox,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from ui.utils import fmt_size, fmt_duration


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

        # En-tête
        header_row = QHBoxLayout()
        title = QLabel("Historique des sauvegardes")
        f = QFont()
        f.setPointSize(15)
        f.setBold(True)
        title.setFont(f)
        header_row.addWidget(title)
        header_row.addStretch()

        btn_refresh = QPushButton("Actualiser")
        btn_refresh.clicked.connect(self.refresh)
        header_row.addWidget(btn_refresh)
        layout.addLayout(header_row)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep)

        # Tableau d'historique
        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels([
            "Date", "Copiés", "Inchangés", "Erreurs", "Durée", "Disques sources",
        ])
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(False)
        self._table.setSortingEnabled(False)

        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)

        layout.addWidget(self._table, stretch=1)

        # Label "aucun historique"
        self._empty_label = QLabel(
            "Aucun historique de sauvegarde disponible.\n"
            "Lancez votre première sauvegarde pour commencer."
        )
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setVisible(False)
        layout.addWidget(self._empty_label)

        self.refresh()

    # ── Refresh ───────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        entries = self._load_history()

        self._table.setRowCount(0)

        if not entries:
            self._table.setVisible(False)
            self._empty_label.setVisible(True)
            return

        self._table.setVisible(True)
        self._empty_label.setVisible(False)

        # Les entrées les plus récentes en premier
        for entry in reversed(entries):
            self._add_row(entry)

    def _add_row(self, entry: dict) -> None:
        row = self._table.rowCount()
        self._table.insertRow(row)

        # Date
        self._table.setItem(row, 0, QTableWidgetItem(entry.get("date", "—")))

        # Fichiers copiés
        copied = entry.get("files_copied", 0)
        item_copied = QTableWidgetItem(str(copied))
        item_copied.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._table.setItem(row, 1, item_copied)

        # Fichiers inchangés
        unchanged = entry.get("files_unchanged", 0)
        item_unch = QTableWidgetItem(str(unchanged))
        item_unch.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._table.setItem(row, 2, item_unch)

        # Erreurs — colorées en rouge si non nulles
        errors = entry.get("errors", 0)
        item_err = QTableWidgetItem(str(errors) if errors else "—")
        item_err.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        if errors:
            item_err.setForeground(Qt.GlobalColor.red)
        self._table.setItem(row, 3, item_err)

        # Durée
        duration_s = entry.get("duration_s", 0.0)
        self._table.setItem(row, 4, QTableWidgetItem(fmt_duration(duration_s)))

        # Disques sources
        sources = entry.get("sources", [])
        src_text = ", ".join(sources) if sources else "—"
        item_src = QTableWidgetItem(src_text)
        item_src.setToolTip(src_text)
        self._table.setItem(row, 5, item_src)

    # ── Chargement ────────────────────────────────────────────────────────────

    def _load_history(self) -> list[dict]:
        """
        Lit backup_history.jsonl (format JSON Lines).
        Retourne la liste des entrées (oldest first).
        """
        path = self._data_dir / "backup_history.jsonl"
        if not path.exists():
            # Compatibilité ascendante : si seul last_backup.json existe
            last = self._load_last_backup_json()
            return [last] if last else []

        entries = []
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        except Exception:
            pass
        return entries

    def _load_last_backup_json(self) -> dict | None:
        """Fallback : lit last_backup.json si backup_history.jsonl n'existe pas encore."""
        p = self._data_dir / "last_backup.json"
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                pass
        return None
