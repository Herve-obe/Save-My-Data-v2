"""
settings_page.py — Page de paramètres de Save My Data.

Sections :
  - Mode de sauvegarde (heure inline à côté de chaque option concernée)
  - Démarrage automatique
  - Comportement à la fermeture de la fenêtre
  - Menu contextuel Windows (clic droit Explorateur)
  - Destination de restauration par défaut
  - Filtres de sauvegarde (extensions, dossiers, taille max)
  - Thème (sombre / clair / du bureau)
"""

import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QRadioButton, QButtonGroup, QTimeEdit, QComboBox,
    QGroupBox, QScrollArea, QMessageBox, QListWidget, QLineEdit,
    QSpinBox,
)
from PySide6.QtCore import QTime, Signal
from PySide6.QtGui import QFont

import config


class SettingsPage(QWidget):
    """Page de paramètres."""

    settings_saved = Signal()   # émis après chaque enregistrement réussi

    def __init__(self, data_dir: Path, parent=None):
        super().__init__(parent)
        self._data_dir = data_dir
        self._syncing_time = False   # Empêche la boucle de synchro des QTimeEdit
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
        title = QLabel("Paramètres")
        f = QFont()
        f.setPointSize(15)
        f.setBold(True)
        title.setFont(f)
        layout.addWidget(title)

        layout.addWidget(self._build_backup_group())
        layout.addWidget(self._build_autostart_group())
        layout.addWidget(self._build_close_group())
        layout.addWidget(self._build_ctx_group())
        layout.addWidget(self._build_restore_group())
        layout.addWidget(self._build_filters_group())
        layout.addWidget(self._build_theme_group())

        # Bouton Enregistrer
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_save = QPushButton("Enregistrer les paramètres")
        btn_save.setStyleSheet(
            "QPushButton { background: #555; color: white; border: none; "
            "border-radius: 6px; padding: 8px 24px; font-weight: bold; }"
            "QPushButton:hover { background: #666; }"
        )
        btn_save.clicked.connect(self._save)
        btn_row.addWidget(btn_save)
        layout.addLayout(btn_row)

        layout.addStretch()

        wrapper = QVBoxLayout(self)
        wrapper.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(content)
        wrapper.addWidget(scroll)

        self.refresh()

    # ── Sections ──────────────────────────────────────────────────────────────

    def _build_backup_group(self) -> QGroupBox:
        group = QGroupBox("Mode de sauvegarde")
        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        self._mode_group = QButtonGroup(self)

        # Option 1 : à l'extinction
        self._radio_shutdown = QRadioButton("À l'extinction de l'ordinateur")
        self._mode_group.addButton(self._radio_shutdown)
        layout.addWidget(self._radio_shutdown)

        # Option 2 : heure fixe  [HH:mm]
        row2 = QHBoxLayout()
        self._radio_scheduled = QRadioButton("À heure fixe chaque jour :")
        self._mode_group.addButton(self._radio_scheduled)
        row2.addWidget(self._radio_scheduled)
        self._time_sched = QTimeEdit()
        self._time_sched.setDisplayFormat("HH:mm")
        self._time_sched.setFixedWidth(80)
        row2.addWidget(self._time_sched)
        row2.addStretch()
        layout.addLayout(row2)

        # Option 3 : les deux  [HH:mm]
        row3 = QHBoxLayout()
        self._radio_both = QRadioButton("Les deux (extinction + heure fixe) :")
        self._mode_group.addButton(self._radio_both)
        row3.addWidget(self._radio_both)
        self._time_both = QTimeEdit()
        self._time_both.setDisplayFormat("HH:mm")
        self._time_both.setFixedWidth(80)
        row3.addWidget(self._time_both)
        row3.addStretch()
        layout.addLayout(row3)

        # Les deux QTimeEdit partagent la même valeur → synchronisation
        self._time_sched.timeChanged.connect(self._sync_sched_to_both)
        self._time_both.timeChanged.connect(self._sync_both_to_sched)

        # Activer/désactiver les QTimeEdit selon la sélection
        for r in (self._radio_shutdown, self._radio_scheduled, self._radio_both):
            r.toggled.connect(self._update_time_enabled)

        return group

    def _build_autostart_group(self) -> QGroupBox:
        group = QGroupBox("Démarrage automatique")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        self._autostart_group = QButtonGroup(self)
        self._radio_auto_on  = QRadioButton("Lancer Save My Data au démarrage de Windows")
        self._radio_auto_off = QRadioButton("Ne pas lancer automatiquement")
        for r in (self._radio_auto_on, self._radio_auto_off):
            self._autostart_group.addButton(r)
            layout.addWidget(r)

        return group

    def _build_close_group(self) -> QGroupBox:
        group = QGroupBox("Comportement à la fermeture de la fenêtre")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        self._close_group = QButtonGroup(self)
        self._radio_close_minimize = QRadioButton(
            "Réduire dans le systray (l'application reste active en arrière-plan)"
        )
        self._radio_close_quit = QRadioButton(
            "Fermer complètement l'application"
        )
        for r in (self._radio_close_minimize, self._radio_close_quit):
            self._close_group.addButton(r)
            layout.addWidget(r)

        return group

    def _build_ctx_group(self) -> QGroupBox:
        group = QGroupBox("Intégration Windows — clic droit Explorateur")
        layout = QHBoxLayout(group)

        ctx_lbl = QLabel(
            "« Restaurer depuis le dernier back-up » dans le menu\n"
            "clic droit de l'Explorateur Windows :"
        )
        ctx_lbl.setWordWrap(True)
        layout.addWidget(ctx_lbl, stretch=1)

        self._btn_ctx = QPushButton("")
        self._btn_ctx.setMinimumWidth(180)
        self._btn_ctx.clicked.connect(self._toggle_ctx)
        layout.addWidget(self._btn_ctx)

        return group

    def _build_restore_group(self) -> QGroupBox:
        group = QGroupBox("Destination de restauration par défaut")
        layout = QHBoxLayout(group)

        layout.addWidget(QLabel("Destination :"))
        self._restore_combo = QComboBox()
        self._restore_combo.addItem("Emplacement d'origine", "original")
        self._restore_combo.addItem("Me demander à chaque fois", "ask")
        layout.addWidget(self._restore_combo)
        layout.addStretch()

        return group

    def _build_filters_group(self) -> QGroupBox:
        group = QGroupBox("Filtres de sauvegarde")
        layout = QVBoxLayout(group)
        layout.setSpacing(14)

        # ── Extensions exclues ────────────────────────────────────────────────
        lbl_ext = QLabel("Extensions exclues :")
        layout.addWidget(lbl_ext)

        ext_row = QHBoxLayout()
        ext_row.setSpacing(10)

        self._ext_list = QListWidget()
        self._ext_list.setFixedHeight(88)
        ext_row.addWidget(self._ext_list, stretch=1)

        ext_ctrl = QVBoxLayout()
        ext_ctrl.setSpacing(4)
        self._ext_input = QLineEdit()
        self._ext_input.setPlaceholderText(".tmp")
        self._ext_input.setFixedWidth(110)
        self._ext_input.returnPressed.connect(self._add_extension)
        ext_ctrl.addWidget(self._ext_input)
        btn_add_ext = QPushButton("Ajouter")
        btn_add_ext.setFixedWidth(110)
        btn_add_ext.clicked.connect(self._add_extension)
        ext_ctrl.addWidget(btn_add_ext)
        btn_del_ext = QPushButton("Supprimer")
        btn_del_ext.setFixedWidth(110)
        btn_del_ext.clicked.connect(self._del_extension)
        ext_ctrl.addWidget(btn_del_ext)
        ext_ctrl.addStretch()
        ext_row.addLayout(ext_ctrl)
        layout.addLayout(ext_row)

        # ── Dossiers exclus ───────────────────────────────────────────────────
        lbl_folder = QLabel("Dossiers exclus :")
        layout.addWidget(lbl_folder)

        folder_row = QHBoxLayout()
        folder_row.setSpacing(10)

        self._folder_list = QListWidget()
        self._folder_list.setFixedHeight(88)
        folder_row.addWidget(self._folder_list, stretch=1)

        folder_ctrl = QVBoxLayout()
        folder_ctrl.setSpacing(4)
        self._folder_input = QLineEdit()
        self._folder_input.setPlaceholderText("node_modules")
        self._folder_input.setFixedWidth(110)
        self._folder_input.returnPressed.connect(self._add_folder)
        folder_ctrl.addWidget(self._folder_input)
        btn_add_folder = QPushButton("Ajouter")
        btn_add_folder.setFixedWidth(110)
        btn_add_folder.clicked.connect(self._add_folder)
        folder_ctrl.addWidget(btn_add_folder)
        btn_del_folder = QPushButton("Supprimer")
        btn_del_folder.setFixedWidth(110)
        btn_del_folder.clicked.connect(self._del_folder)
        folder_ctrl.addWidget(btn_del_folder)
        folder_ctrl.addStretch()
        folder_row.addLayout(folder_ctrl)
        layout.addLayout(folder_row)

        # ── Taille maximale par fichier ───────────────────────────────────────
        size_row = QHBoxLayout()
        size_row.addWidget(QLabel("Taille maximale par fichier :"))
        self._max_size_spin = QSpinBox()
        self._max_size_spin.setRange(0, 100_000)
        self._max_size_spin.setSuffix(" Mo")
        self._max_size_spin.setSpecialValueText("Sans limite")
        self._max_size_spin.setFixedWidth(150)
        size_row.addWidget(self._max_size_spin)
        size_row.addStretch()
        layout.addLayout(size_row)

        return group

    def _build_theme_group(self) -> QGroupBox:
        group = QGroupBox("Apparence")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        self._theme_group = QButtonGroup(self)
        self._radio_dark   = QRadioButton("Thème sombre (noir et gris foncés)")
        self._radio_light  = QRadioButton("Thème clair")
        self._radio_system = QRadioButton("Thème du bureau (suit le thème Windows)")
        for r in (self._radio_dark, self._radio_light, self._radio_system):
            self._theme_group.addButton(r)
            layout.addWidget(r)

        return group

    # ── Refresh ───────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        cfg = config.load()

        # Mode
        mode = cfg.get("backup", {}).get("mode", "shutdown")
        {
            "shutdown":  self._radio_shutdown,
            "scheduled": self._radio_scheduled,
            "both":      self._radio_both,
        }.get(mode, self._radio_shutdown).setChecked(True)

        # Heure
        sched_time = cfg.get("backup", {}).get("scheduled_time", "22:00")
        parts = sched_time.split(":")
        h = int(parts[0]) if parts else 22
        m = int(parts[1]) if len(parts) > 1 else 0
        qt = QTime(h, m)
        self._time_sched.setTime(qt)
        self._time_both.setTime(qt)
        self._update_time_enabled()

        # Démarrage automatique
        autostart = cfg.get("autostart", True)
        (self._radio_auto_on if autostart else self._radio_auto_off).setChecked(True)

        # Comportement fermeture
        close_beh = cfg.get("ui", {}).get("close_behavior", "minimize")
        (self._radio_close_minimize if close_beh == "minimize"
         else self._radio_close_quit).setChecked(True)

        # Menu contextuel
        self._refresh_ctx_btn()

        # Destination restauration
        restore_dest = cfg.get("restore", {}).get("default_destination", "original")
        idx = self._restore_combo.findData(restore_dest)
        if idx >= 0:
            self._restore_combo.setCurrentIndex(idx)

        # Filtres
        filters = cfg.get("filters", {})
        self._ext_list.clear()
        for ext in filters.get("excluded_extensions", []):
            self._ext_list.addItem(ext)
        self._folder_list.clear()
        for folder in filters.get("excluded_folders", []):
            self._folder_list.addItem(folder)
        max_bytes = filters.get("max_size_bytes", 0)
        self._max_size_spin.setValue(max_bytes // (1024 * 1024) if max_bytes > 0 else 0)

        # Thème
        theme = cfg.get("theme", "dark")
        {
            "dark":   self._radio_dark,
            "light":  self._radio_light,
            "system": self._radio_system,
        }.get(theme, self._radio_dark).setChecked(True)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _refresh_ctx_btn(self) -> None:
        from core.registry_manager import is_registered
        if is_registered():
            self._btn_ctx.setText("Désactiver le clic droit")
        else:
            self._btn_ctx.setText("Activer le clic droit")

    def _update_time_enabled(self) -> None:
        needs_time = self._radio_scheduled.isChecked() or self._radio_both.isChecked()
        self._time_sched.setEnabled(needs_time)
        self._time_both.setEnabled(needs_time)

    def _sync_sched_to_both(self, t: QTime) -> None:
        if self._syncing_time:
            return
        self._syncing_time = True
        self._time_both.setTime(t)
        self._syncing_time = False

    def _sync_both_to_sched(self, t: QTime) -> None:
        if self._syncing_time:
            return
        self._syncing_time = True
        self._time_sched.setTime(t)
        self._syncing_time = False

    def _add_extension(self) -> None:
        raw = self._ext_input.text().strip()
        if not raw:
            return
        # Normaliser : ajouter le point si absent, mettre en minuscules
        ext = raw.lower() if raw.startswith(".") else f".{raw.lower()}"
        existing = [self._ext_list.item(i).text()
                    for i in range(self._ext_list.count())]
        if ext not in existing:
            self._ext_list.addItem(ext)
        self._ext_input.clear()

    def _del_extension(self) -> None:
        row = self._ext_list.currentRow()
        if row >= 0:
            self._ext_list.takeItem(row)

    def _add_folder(self) -> None:
        name = self._folder_input.text().strip()
        if not name:
            return
        existing = [self._folder_list.item(i).text()
                    for i in range(self._folder_list.count())]
        if name not in existing:
            self._folder_list.addItem(name)
        self._folder_input.clear()

    def _del_folder(self) -> None:
        row = self._folder_list.currentRow()
        if row >= 0:
            self._folder_list.takeItem(row)

    # ── Enregistrement ────────────────────────────────────────────────────────

    def _save(self) -> None:
        # Mode
        if self._radio_shutdown.isChecked():
            mode = "shutdown"
        elif self._radio_scheduled.isChecked():
            mode = "scheduled"
        else:
            mode = "both"

        sched_time   = self._time_sched.time().toString("HH:mm")
        autostart    = self._radio_auto_on.isChecked()
        close_beh    = ("minimize" if self._radio_close_minimize.isChecked()
                        else "quit")
        restore_dest = self._restore_combo.currentData()

        if self._radio_dark.isChecked():
            theme = "dark"
        elif self._radio_light.isChecked():
            theme = "light"
        else:
            theme = "system"

        # Filtres
        extensions = [self._ext_list.item(i).text()
                      for i in range(self._ext_list.count())]
        folders    = [self._folder_list.item(i).text()
                      for i in range(self._folder_list.count())]
        mb = self._max_size_spin.value()
        max_bytes  = mb * 1024 * 1024 if mb > 0 else 0

        config.set_value("backup.mode", mode)
        config.set_value("backup.scheduled_time", sched_time)
        config.set_value("autostart", autostart)
        config.set_value("ui.close_behavior", close_beh)
        config.set_value("restore.default_destination", restore_dest)
        config.set_value("filters.excluded_extensions", extensions)
        config.set_value("filters.excluded_folders", folders)
        config.set_value("filters.max_size_bytes", max_bytes)
        config.set_value("theme", theme)

        self._apply_autostart(autostart)

        QMessageBox.information(self, "Save My Data", "Paramètres enregistrés.")

        # Notifier le planificateur d'une éventuelle mise à jour
        self.settings_saved.emit()

        # Appliquer le nouveau thème immédiatement
        win = self.window()
        if hasattr(win, "apply_theme"):
            win.apply_theme()

    def _apply_autostart(self, enable: bool) -> None:
        if sys.platform != "win32":
            return
        import winreg

        key_path    = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name    = "SaveMyData"
        main_script = (Path(__file__).parent.parent.parent / "main.py").resolve()

        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE
            ) as key:
                if enable:
                    import sys as _sys
                    if getattr(_sys, "frozen", False):
                        cmd = f'"{_sys.executable}" --autostart'
                    else:
                        cmd = f'"{_sys.executable}" -X utf8 "{main_script}" --autostart'
                    winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, cmd)
                else:
                    try:
                        winreg.DeleteValue(key, app_name)
                    except FileNotFoundError:
                        pass
        except Exception:
            pass

    def _toggle_ctx(self) -> None:
        from core.registry_manager import register, unregister, is_registered

        if is_registered():
            ok, msg = unregister()
        else:
            python_exe  = Path(sys.executable)
            main_script = (Path(__file__).parent.parent.parent / "main.py").resolve()
            ok, msg = register(python_exe, main_script)

        if ok:
            self._refresh_ctx_btn()
            config.set_value("restore.context_menu", is_registered())
        else:
            QMessageBox.warning(self, "Save My Data", f"Échec : {msg}")
