"""
disks_page.py — Configuration des disques source et cible.

Chaque disque est affiché sur une seule ligne :
  [radio/check  C:\\]  [Nom du volume]  [██████░░░░  536 Go libres / 894 Go - 40% utilise]

Les sources peuvent être des disques entiers OU des dossiers personnalisés.
"""

import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QCheckBox, QButtonGroup, QRadioButton, QScrollArea,
    QMessageBox, QGroupBox, QSizePolicy, QApplication, QFileDialog,
)
from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QFont, QPainter, QColor, QPalette

import config


# ── Barre de progression dessinée entièrement à la main ──────────────────────

class DiskProgressBar(QWidget):
    """
    Barre de progression dessinée manuellement (fond + remplissage + texte).

    Indépendante du style Qt et du QSS — garantit un rendu correct en thème
    sombre comme en thème clair, à l'image de l'Explorateur Windows.
    """

    def __init__(self, pct: int, custom_text: str = "", parent=None):
        super().__init__(parent)
        self._pct  = max(0, min(100, pct))
        self._text = custom_text
        self.setFixedHeight(26)
        self.setMinimumWidth(200)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        r      = self.rect()
        radius = 4

        # 1. Fond de la barre — adaptatif au thème (BUG-05)
        app = QApplication.instance()
        if app is not None:
            window_color = app.palette().color(QPalette.ColorRole.Window)
            is_dark = window_color.lightness() < 128
        else:
            is_dark = True
        bg_color = QColor(55, 55, 55) if is_dark else QColor(200, 200, 208)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bg_color)
        painter.drawRoundedRect(r, radius, radius)

        # 2. Remplissage proportionnel au %
        if self._pct > 0:
            fill_w = max(radius * 2, int(r.width() * self._pct / 100))
            fill_r = QRect(r.x(), r.y(), fill_w, r.height())
            fill_color = (QColor(180, 50, 50)    # rouge si > 85 %
                          if self._pct > 85
                          else QColor(70, 130, 200))  # bleu acier sinon
            painter.setBrush(fill_color)
            painter.drawRoundedRect(fill_r, radius, radius)

        # 3. Texte centré avec ombre portée
        if self._text:
            f = self.font()
            painter.setFont(f)
            painter.setPen(QColor(0, 0, 0, 180))
            painter.drawText(r.adjusted(1, 1, 1, 1),
                             Qt.AlignmentFlag.AlignCenter, self._text)
            painter.setPen(QColor(255, 255, 255, 240))
            painter.drawText(r, Qt.AlignmentFlag.AlignCenter, self._text)

        painter.end()


# ── Utilitaires ───────────────────────────────────────────────────────────────

def _get_volume_label(mountpoint: str) -> str:
    """Retourne le nom Windows du volume (ex. 'Local Disk', 'BackUp')."""
    if sys.platform != "win32":
        return ""
    try:
        import ctypes
        buf = ctypes.create_unicode_buffer(261)
        ctypes.windll.kernel32.GetVolumeInformationW(
            ctypes.c_wchar_p(mountpoint), buf, 261,
            None, None, None, None, 0,
        )
        return buf.value
    except Exception:
        return ""


def _fmt_gb(b: int) -> str:
    gb = b / 1024**3
    return f"{gb:.1f} Go" if gb < 100 else f"{gb:.0f} Go"


def _clear_layout(layout) -> None:
    while layout.count():
        child = layout.takeAt(0)
        if child.widget():
            child.widget().deleteLater()
        elif child.layout():
            _clear_layout(child.layout())


# ── Carte disque (une ligne) ──────────────────────────────────────────────────

class DiskCard(QFrame):
    """
    Carte d'un disque sur une seule ligne :
      [selector]  [Nom du volume  ]  [DiskProgressBar ▓▓▓▓░░░  texte capacité]
    """

    def __init__(self, mountpoint: str, is_target: bool,
                 total: int, used: int, free: int,
                 checked: bool = False, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(12)

        # ── Sélecteur (radio ou checkbox) ─────────────────────────────────────
        mp_label = mountpoint.rstrip("/\\") + "\\"   # normalize → "C:\"
        if is_target:
            self._selector = QRadioButton(mp_label)
        else:
            self._selector = QCheckBox(mp_label)
        self._selector.setChecked(checked)
        self._selector.setFixedWidth(58)
        layout.addWidget(self._selector)

        # ── Nom du volume ──────────────────────────────────────────────────────
        vol = _get_volume_label(mountpoint)
        lbl_name = QLabel(vol if vol else "")
        if vol:
            f = QFont()
            f.setBold(True)
            lbl_name.setFont(f)
        lbl_name.setFixedWidth(170)
        lbl_name.setToolTip(vol)
        layout.addWidget(lbl_name)

        # ── Barre de progression avec texte intégré ────────────────────────────
        pct = int(used / total * 100) if total > 0 else 0
        bar_text = (
            f"{_fmt_gb(free)} libres / {_fmt_gb(total)}"
            f"  —  {pct}% utilisé"
        )

        bar = DiskProgressBar(pct, bar_text)
        bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(bar, stretch=1)

    @property
    def selector(self) -> QRadioButton | QCheckBox:
        return self._selector


class DiskCardError(QFrame):
    """Carte pour un disque inaccessible."""

    def __init__(self, mountpoint: str, is_target: bool,
                 checked: bool = False, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(12)

        mp_label = mountpoint.rstrip("/\\") + "\\"
        if is_target:
            self._selector = QRadioButton(mp_label)
        else:
            self._selector = QCheckBox(mp_label)
        self._selector.setChecked(checked)
        layout.addWidget(self._selector)

        vol = _get_volume_label(mountpoint)
        if vol:
            lbl = QLabel(vol)
            f = QFont()
            f.setBold(True)
            lbl.setFont(f)
            layout.addWidget(lbl)

        lbl_err = QLabel("(inaccessible)")
        layout.addWidget(lbl_err)
        layout.addStretch()

    @property
    def selector(self) -> QRadioButton | QCheckBox:
        return self._selector


# ── Page principale ───────────────────────────────────────────────────────────

class DisksPage(QWidget):
    """Page de configuration des disques source et cible."""

    def __init__(self, data_dir: Path, parent=None):
        super().__init__(parent)
        self._data_dir = data_dir
        self._source_checks: dict[str, QCheckBox] = {}
        self._target_radios: dict[str, QRadioButton] = {}
        self._target_group = QButtonGroup(self)
        self._custom_sources: list[str] = []   # dossiers source personnalisés
        self._build_ui()

    # ── Construction ──────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(36, 36, 36, 36)
        layout.setSpacing(24)

        # Titre
        title = QLabel("Mes disques")
        f = QFont()
        f.setPointSize(15)
        f.setBold(True)
        title.setFont(f)
        layout.addWidget(title)

        desc = QLabel(
            "Sélectionnez le disque de sauvegarde (cible) et les sources à "
            "sauvegarder. Les sources peuvent être des disques entiers ou des "
            "dossiers spécifiques."
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # ── Disque cible ──────────────────────────────────────────────────────
        self._target_group_box = QGroupBox("Disque de sauvegarde (cible)")
        tgl = QVBoxLayout(self._target_group_box)
        tgl.setSpacing(6)
        self._target_container = QVBoxLayout()
        self._target_container.setSpacing(4)
        tgl.addLayout(self._target_container)
        layout.addWidget(self._target_group_box)

        # ── Disques sources ───────────────────────────────────────────────────
        self._source_group_box = QGroupBox("Sources à sauvegarder")
        sgl = QVBoxLayout(self._source_group_box)
        sgl.setSpacing(6)

        # Sous-section : disques détectés
        lbl_disks = QLabel("Disques détectés :")
        lbl_disks.setStyleSheet("font-weight: bold; padding-top: 4px;")
        sgl.addWidget(lbl_disks)

        self._source_container = QVBoxLayout()
        self._source_container.setSpacing(4)
        sgl.addLayout(self._source_container)

        # Sous-section : dossiers personnalisés
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        sgl.addWidget(sep)

        custom_header = QHBoxLayout()
        lbl_custom = QLabel("Dossiers spécifiques :")
        lbl_custom.setStyleSheet("font-weight: bold;")
        custom_header.addWidget(lbl_custom)
        custom_header.addStretch()
        btn_add = QPushButton("+ Ajouter un dossier…")
        btn_add.setFixedHeight(28)
        btn_add.clicked.connect(self._add_custom_source)
        custom_header.addWidget(btn_add)
        sgl.addLayout(custom_header)

        self._custom_container = QVBoxLayout()
        self._custom_container.setSpacing(4)
        sgl.addLayout(self._custom_container)

        self._lbl_no_custom = QLabel("Aucun dossier spécifique ajouté.")
        self._lbl_no_custom.setStyleSheet("color: #888; font-style: italic; padding: 4px 0;")
        sgl.addWidget(self._lbl_no_custom)

        layout.addWidget(self._source_group_box)

        # ── Boutons ───────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._btn_refresh = QPushButton("Actualiser")
        self._btn_refresh.clicked.connect(self.refresh)
        btn_row.addWidget(self._btn_refresh)

        self._btn_save = QPushButton("Enregistrer")
        self._btn_save.setStyleSheet(
            "QPushButton { background: #555; color: white; border: none; "
            "border-radius: 6px; padding: 8px 24px; font-weight: bold; }"
            "QPushButton:hover { background: #666; }"
        )
        self._btn_save.clicked.connect(self._save)
        btn_row.addWidget(self._btn_save)
        layout.addLayout(btn_row)

        layout.addStretch()

        wrapper = QVBoxLayout(self)
        wrapper.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(content)
        wrapper.addWidget(scroll)

        self.refresh()

    # ── Refresh ───────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        cfg = config.load()
        saved_target  = cfg.get("backup", {}).get("target_disk", "").rstrip("/\\")
        all_sources   = cfg.get("backup", {}).get("source_disks", [])

        _clear_layout(self._target_container)
        _clear_layout(self._source_container)
        self._target_radios.clear()
        self._source_checks.clear()

        for btn in list(self._target_group.buttons()):
            self._target_group.removeButton(btn)

        drives = self._detect_drives()
        detected_mps = {info["mp"].rstrip("/\\") for info in drives}

        # Séparer sources disques et sources dossiers personnalisés
        disk_sources   = {s.rstrip("/\\") for s in all_sources if s.rstrip("/\\") in detected_mps}
        self._custom_sources = [s for s in all_sources if s.rstrip("/\\") not in detected_mps]

        if not drives:
            self._target_container.addWidget(QLabel("Aucun disque détecté."))
            self._source_container.addWidget(QLabel("Aucun disque détecté."))
        else:
            for info in drives:
                mp      = info["mp"]
                mp_norm = mp.rstrip("/\\")
                is_target_checked = (mp_norm == saved_target)
                is_source_checked = (mp_norm in disk_sources)

                if "total" in info:
                    target_card = DiskCard(mp, True,
                                           info["total"], info["used"], info["free"],
                                           checked=is_target_checked)
                    source_card = DiskCard(mp, False,
                                           info["total"], info["used"], info["free"],
                                           checked=is_source_checked)
                else:
                    target_card = DiskCardError(mp, True, checked=is_target_checked)
                    source_card = DiskCardError(mp, False, checked=is_source_checked)

                self._target_radios[mp] = target_card.selector
                self._target_group.addButton(target_card.selector)
                self._target_container.addWidget(target_card)

                self._source_checks[mp] = source_card.selector
                self._source_container.addWidget(source_card)

        self._render_custom_sources()

    def _render_custom_sources(self) -> None:
        """Reconstruit l'affichage des dossiers personnalisés."""
        _clear_layout(self._custom_container)
        if self._custom_sources:
            self._lbl_no_custom.setVisible(False)
            for path_str in self._custom_sources:
                self._custom_container.addWidget(
                    self._make_custom_row(path_str)
                )
        else:
            self._lbl_no_custom.setVisible(True)

    def _make_custom_row(self, path_str: str) -> QFrame:
        """Crée une ligne affichant un dossier personnalisé avec bouton supprimer."""
        row = QFrame()
        row.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(14, 6, 14, 6)
        layout.setSpacing(10)

        lbl = QLabel(path_str)
        lbl.setToolTip(path_str)
        layout.addWidget(lbl, stretch=1)

        # Infos de taille si dossier accessible
        p = Path(path_str)
        if p.exists():
            try:
                import psutil
                usage = psutil.disk_usage(str(p))
                free_gb  = usage.free  / 1024**3
                total_gb = usage.total / 1024**3
                lbl_size = QLabel(f"{free_gb:.1f} Go libres / {total_gb:.0f} Go")
                lbl_size.setStyleSheet("color: #888; font-size: 11px;")
                layout.addWidget(lbl_size)
            except Exception:
                pass
        else:
            lbl_err = QLabel("(inaccessible)")
            lbl_err.setStyleSheet("color: #f59e0b; font-size: 11px;")
            layout.addWidget(lbl_err)

        btn_del = QPushButton("Retirer")
        btn_del.setFixedSize(60, 24)
        btn_del.setStyleSheet("color: #c0392b;")
        btn_del.clicked.connect(lambda: self._remove_custom_source(path_str))
        layout.addWidget(btn_del)

        return row

    # ── Gestion des sources personnalisées ────────────────────────────────────

    def _add_custom_source(self) -> None:
        """Ouvre un sélecteur de dossier et l'ajoute aux sources personnalisées."""
        folder = QFileDialog.getExistingDirectory(
            self, "Sélectionner un dossier source"
        )
        if not folder:
            return
        folder = str(Path(folder))  # normalise les séparateurs

        # Déduplication
        if folder in self._custom_sources:
            return

        # Vérifier que ce n'est pas un disque déjà sélectionnable comme source
        drives = self._detect_drives()
        detected_mps = {info["mp"].rstrip("/\\") for info in drives}
        if folder.rstrip("/\\") in detected_mps:
            QMessageBox.information(
                self, "Save My Data",
                "Ce chemin correspond à un disque entier.\n"
                "Cochez-le directement dans la section « Disques détectés »."
            )
            return

        self._custom_sources.append(folder)
        self._render_custom_sources()

    def _remove_custom_source(self, path_str: str) -> None:
        if path_str in self._custom_sources:
            self._custom_sources.remove(path_str)
        self._render_custom_sources()

    def _detect_drives(self) -> list[dict]:
        try:
            import psutil
        except ImportError:
            return []

        drives = []
        try:
            partitions = psutil.disk_partitions(all=False)
        except Exception:
            return []

        for part in partitions:
            mp    = part.mountpoint
            entry = {"mp": mp}
            try:
                usage = psutil.disk_usage(mp)
                entry["total"] = usage.total
                entry["used"]  = usage.used
                entry["free"]  = usage.free
            except (PermissionError, OSError):
                pass
            drives.append(entry)

        return drives

    # ── Enregistrement ────────────────────────────────────────────────────────

    def _save(self) -> None:
        target = next(
            (mp for mp, r in self._target_radios.items() if r.isChecked()), ""
        )
        disk_sources   = [mp for mp, chk in self._source_checks.items() if chk.isChecked()]
        all_sources    = disk_sources + self._custom_sources

        if not target:
            QMessageBox.warning(self, "Save My Data",
                                "Veuillez sélectionner un disque cible.")
            return
        if not all_sources:
            QMessageBox.warning(self, "Save My Data",
                                "Veuillez sélectionner au moins une source.")
            return

        target_norm = target.rstrip("/\\")
        if target_norm in {s.rstrip("/\\") for s in disk_sources}:
            QMessageBox.warning(
                self, "Save My Data",
                "Le disque cible ne peut pas être aussi un disque source."
            )
            return

        # Vérifier qu'aucun dossier personnalisé n'est sur le disque cible
        for s in self._custom_sources:
            try:
                if Path(s).drive.rstrip(":").upper() == target_norm.rstrip(":").upper():
                    reply = QMessageBox.question(
                        self, "Save My Data",
                        f"Le dossier source « {s} » se trouve sur le disque cible.\n"
                        "Sauvegarder sur le même disque réduit la protection.\n\n"
                        "Continuer quand même ?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    )
                    if reply != QMessageBox.StandardButton.Yes:
                        return
                    break
            except Exception:
                pass

        config.set_value("backup.target_disk", target)
        config.set_value("backup.source_disks", all_sources)
        QMessageBox.information(self, "Save My Data",
                                "Configuration des disques enregistrée.")
