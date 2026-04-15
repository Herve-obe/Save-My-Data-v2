"""
disks_page.py — Configuration des disques source et cible.

Chaque disque est affiché sur une seule ligne :
  [radio/check  C:\\]  [Nom du volume]  [██████░░░░  536 Go libres / 894 Go - 40% utilise]

La barre de progression affiche les capacités directement en texte superposé,
comme dans la fenêtre des disques Windows.
"""

import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QCheckBox, QButtonGroup, QRadioButton, QScrollArea,
    QMessageBox, QGroupBox, QSizePolicy, QApplication,
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
            "Sélectionnez le disque de sauvegarde (cible) et les disques "
            "à sauvegarder (sources). Le disque cible ne peut pas être une source."
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
        self._source_group_box = QGroupBox("Disques à sauvegarder (sources)")
        sgl = QVBoxLayout(self._source_group_box)
        sgl.setSpacing(6)
        self._source_container = QVBoxLayout()
        self._source_container.setSpacing(4)
        sgl.addLayout(self._source_container)
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
        saved_sources = {s.rstrip("/\\") for s in cfg.get("backup", {}).get("source_disks", [])}

        _clear_layout(self._target_container)
        _clear_layout(self._source_container)
        self._target_radios.clear()
        self._source_checks.clear()

        for btn in list(self._target_group.buttons()):
            self._target_group.removeButton(btn)

        drives = self._detect_drives()

        if not drives:
            self._target_container.addWidget(QLabel("Aucun disque détecté."))
            self._source_container.addWidget(QLabel("Aucun disque détecté."))
            return

        for info in drives:
            mp      = info["mp"]
            mp_norm = mp.rstrip("/\\")
            is_target_checked = (mp_norm == saved_target)
            is_source_checked = (mp_norm in saved_sources)

            if "total" in info:
                # Carte cible
                target_card = DiskCard(mp, True,
                                       info["total"], info["used"], info["free"],
                                       checked=is_target_checked)
                # Carte source
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
        sources = [mp for mp, chk in self._source_checks.items() if chk.isChecked()]

        if not target:
            QMessageBox.warning(self, "Save My Data",
                                "Veuillez sélectionner un disque cible.")
            return
        if not sources:
            QMessageBox.warning(self, "Save My Data",
                                "Veuillez sélectionner au moins un disque source.")
            return
        if target.rstrip("/\\") in {s.rstrip("/\\") for s in sources}:
            QMessageBox.warning(
                self, "Save My Data",
                "Le disque cible ne peut pas être aussi un disque source."
            )
            return

        config.set_value("backup.target_disk", target)
        config.set_value("backup.source_disks", sources)
        QMessageBox.information(self, "Save My Data",
                                "Configuration des disques enregistrée.")
