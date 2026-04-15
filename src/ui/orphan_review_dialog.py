"""
orphan_review_dialog.py — Interface de révision des fichiers orphelins.

Affiché au démarrage (ou depuis le menu systray) quand des fichiers ont
été supprimés de la source depuis la dernière sauvegarde.

Pour chaque orphelin, l'utilisateur choisit :
  - Conserver          : garder dans la sauvegarde, ne plus signaler
  - Supprimer          : effacer définitivement de la sauvegarde
  - Restaurer          : recopier depuis la sauvegarde vers son emplacement d'origine
"""

import shutil
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame,
    QTableWidget, QTableWidgetItem, QComboBox,
    QHeaderView, QAbstractItemView, QMessageBox,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from core.orphan_manager import OrphanManager, OrphanEntry

# BUG-02 : _fmt_size centralisé dans ui.utils (plus de duplication)
from ui.utils import fmt_size as _fmt_size


# ── Constantes d'action ───────────────────────────────────────────────────────

ACTION_KEEP    = "Conserver dans la sauvegarde"
ACTION_DELETE  = "Supprimer de la sauvegarde"
ACTION_RESTORE = "Restaurer sur la source"

ACTIONS = [ACTION_KEEP, ACTION_DELETE, ACTION_RESTORE]


# ── Dialogue principal ────────────────────────────────────────────────────────

class OrphanReviewDialog(QDialog):
    """
    Fenêtre listant tous les fichiers orphelins avec un sélecteur d'action
    par ligne et des boutons d'action globale.
    """

    def __init__(self, entries: list[OrphanEntry], data_dir: Path, parent=None):
        super().__init__(parent)
        self._entries = entries
        self._manager = OrphanManager(data_dir)
        self._combos: list[QComboBox] = []

        self.setWindowTitle("Save My Data — Fichiers à réviser")
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setMinimumSize(820, 460)
        self._build_ui()

    # ── Construction ──────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(14)
        root.setContentsMargins(24, 24, 24, 24)

        # ── En-tête ───────────────────────────────────────────────────────────
        n = len(self._entries)

        title = QLabel(f"{n} fichier{'s' if n > 1 else ''} orphelin{'s' if n > 1 else ''} détecté{'s' if n > 1 else ''}")
        font_title = QFont()
        font_title.setPointSize(12)
        font_title.setBold(True)
        title.setFont(font_title)
        root.addWidget(title)

        desc = QLabel(
            "Ces fichiers ont été supprimés de votre disque source "
            "mais sont toujours présents dans votre sauvegarde.\n"
            "Choisissez l'action souhaitée pour chacun d'eux, "
            "puis cliquez sur Valider."
        )
        desc.setWordWrap(True)
        root.addWidget(desc)

        # ── Tableau ───────────────────────────────────────────────────────────
        self._table = QTableWidget(n, 5)
        self._table.setHorizontalHeaderLabels(
            ["Fichier", "Chemin d'origine", "Détecté le", "Taille", "Action"]
        )
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(False)

        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)

        for i, entry in enumerate(self._entries):
            self._fill_row(i, entry)

        root.addWidget(self._table)

        # ── Séparateur ────────────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        root.addWidget(sep)

        # ── Boutons ───────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()

        btn_keep_all = QPushButton("Tout conserver")
        btn_keep_all.setToolTip("Conserver tous les fichiers dans la sauvegarde")
        btn_keep_all.clicked.connect(lambda: self._set_all(ACTION_KEEP))
        btn_row.addWidget(btn_keep_all)

        btn_del_all = QPushButton("Tout supprimer")
        btn_del_all.setToolTip("Supprimer tous les orphelins de la sauvegarde")
        btn_del_all.setStyleSheet("color: #c0392b;")
        btn_del_all.clicked.connect(lambda: self._set_all(ACTION_DELETE))
        btn_row.addWidget(btn_del_all)

        btn_row.addStretch()

        btn_later = QPushButton("Plus tard")
        btn_later.setToolTip("Fermer sans appliquer — les orphelins resteront en attente")
        btn_later.clicked.connect(self.reject)
        btn_row.addWidget(btn_later)

        btn_apply = QPushButton("Valider les actions")
        btn_apply.setDefault(True)
        btn_apply.setMinimumWidth(170)
        btn_apply.clicked.connect(self._apply)
        btn_row.addWidget(btn_apply)

        root.addLayout(btn_row)

    def _fill_row(self, i: int, entry: OrphanEntry) -> None:
        """Remplit une ligne du tableau pour un orphelin."""
        target = Path(entry.target_path)

        # Nom du fichier (tooltip = chemin complet dans la sauvegarde)
        item_name = QTableWidgetItem(target.name)
        item_name.setToolTip(f"Sauvegardé ici :\n{entry.target_path}")
        self._table.setItem(i, 0, item_name)

        # Chemin d'origine (tooltip = chemin complet)
        item_src = QTableWidgetItem(entry.source_path)
        item_src.setToolTip(entry.source_path)
        self._table.setItem(i, 1, item_src)

        # Date de détection (format court)
        self._table.setItem(i, 2, QTableWidgetItem(entry.detected_at[:10]))

        # Taille — BUG-02 : utilise fmt_size centralisé
        item_size = QTableWidgetItem(_fmt_size(entry.size))
        item_size.setTextAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self._table.setItem(i, 3, item_size)

        # Combo action
        combo = QComboBox()
        combo.addItems(ACTIONS)
        combo.setMinimumWidth(220)
        self._table.setCellWidget(i, 4, combo)
        self._combos.append(combo)

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _set_all(self, action: str) -> None:
        """Applique la même action à tous les combos."""
        for combo in self._combos:
            combo.setCurrentText(action)

    def _apply(self) -> None:
        """Applique les actions choisies et ferme le dialogue."""
        kept = deleted = restored = 0
        errors: list[str] = []

        for entry, combo in zip(self._entries, self._combos):
            action = combo.currentText()

            if action == ACTION_KEEP:
                self._manager.apply_action(entry.target_path, "keep")
                kept += 1

            elif action == ACTION_DELETE:
                ok, msg = self._manager.apply_action(entry.target_path, "delete")
                if ok:
                    deleted += 1
                else:
                    errors.append(f"{Path(entry.target_path).name} : {msg}")

            elif action == ACTION_RESTORE:
                ok, msg = self._restore_file(entry)
                if ok:
                    # Après restauration réussie → retirer de la sauvegarde
                    self._manager.apply_action(entry.target_path, "delete")
                    restored += 1
                else:
                    errors.append(f"{Path(entry.target_path).name} : {msg}")

        self._manager.clear_resolved()

        # ── Résumé ────────────────────────────────────────────────────────────
        parts = []
        if kept:     parts.append(f"{kept} conservé{'s' if kept > 1 else ''}")
        if deleted:  parts.append(f"{deleted} supprimé{'s' if deleted > 1 else ''} de la sauvegarde")
        if restored: parts.append(f"{restored} restauré{'s' if restored > 1 else ''} sur la source")
        summary = ", ".join(parts) if parts else "Aucune modification."

        if errors:
            QMessageBox.warning(
                self, "Certaines actions ont échoué",
                summary + "\n\nErreurs :\n" + "\n".join(f"  • {e}" for e in errors),
            )
        else:
            QMessageBox.information(self, "Terminé", summary)

        self.accept()

    # ── Restauration ──────────────────────────────────────────────────────────

    def _restore_file(self, entry: OrphanEntry) -> tuple[bool, str]:
        """
        Copie le fichier depuis la sauvegarde vers son emplacement d'origine.

        BUG-03 FIX : Le fichier de destination est d'abord envoyé à la Corbeille
        (si il existe), permettant un undo. Utilise la même approche que
        restore_engine.restore() pour garantir la cohérence.
        """
        src = Path(entry.target_path)   # Dans la sauvegarde
        dst = Path(entry.source_path)   # Destination d'origine

        if not src.exists():
            return False, "Fichier introuvable dans la sauvegarde."

        # Envoi à la Corbeille si un fichier existe déjà à la destination (BUG-03)
        if dst.exists():
            try:
                import send2trash
                send2trash.send2trash(str(dst))
            except ImportError:
                pass  # send2trash non disponible — on continue sans Corbeille
            except Exception as exc:
                return False, f"Impossible d'envoyer à la Corbeille : {exc}"

        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            return True, "OK"
        except PermissionError:
            return False, "Permission refusée sur le disque source."
        except OSError as exc:
            return False, str(exc)
