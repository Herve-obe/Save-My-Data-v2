"""
main_window.py — Fenêtre principale de Save My Data.

Navigation par barre latérale → QStackedWidget.
Pages : Tableau de bord, Mes disques, Paramètres, Restaurer, Historique.
"""

import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QButtonGroup, QFrame, QStackedWidget, QLabel,
    QApplication,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QCloseEvent, QPalette, QColor

from ui.pages.dashboard_page import DashboardPage
from ui.pages.disks_page import DisksPage
from ui.pages.settings_page import SettingsPage
from ui.pages.restore_page import RestorePage
from ui.pages.history_page import HistoryPage


# ── Version ───────────────────────────────────────────────────────────────────

def _get_version() -> str:
    """Lit la version de l'application depuis la configuration."""
    import config as _cfg
    return _cfg.get("version", "1.0.0")


# ── Détection du thème système ────────────────────────────────────────────────

def _detect_system_theme() -> str:
    """Détecte le thème du bureau (Windows/macOS/fallback Qt)."""
    if sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            ) as k:
                val, _ = winreg.QueryValueEx(k, "AppsUseLightTheme")
                return "light" if val == 1 else "dark"
        except Exception:
            pass
    # Fallback via Qt (PySide6 ≥ 6.5)
    try:
        from PySide6.QtCore import Qt as _Qt
        scheme = QApplication.styleHints().colorScheme()
        return "dark" if scheme == _Qt.ColorScheme.Dark else "light"
    except Exception:
        pass
    return "dark"


# ── Palettes ──────────────────────────────────────────────────────────────────

def dark_palette() -> QPalette:
    """Palette sombre : noirs et gris foncés, sans bleu."""
    p = QPalette()
    p.setColor(QPalette.ColorRole.Window,          QColor(28, 28, 28))
    p.setColor(QPalette.ColorRole.WindowText,      QColor(215, 215, 215))
    p.setColor(QPalette.ColorRole.Base,            QColor(40, 40, 40))
    p.setColor(QPalette.ColorRole.AlternateBase,   QColor(34, 34, 34))
    p.setColor(QPalette.ColorRole.ToolTipBase,     QColor(28, 28, 28))
    p.setColor(QPalette.ColorRole.ToolTipText,     QColor(215, 215, 215))
    p.setColor(QPalette.ColorRole.Text,            QColor(215, 215, 215))
    p.setColor(QPalette.ColorRole.Button,          QColor(50, 50, 50))
    p.setColor(QPalette.ColorRole.ButtonText,      QColor(215, 215, 215))
    p.setColor(QPalette.ColorRole.BrightText,      QColor(255, 255, 255))
    p.setColor(QPalette.ColorRole.Link,            QColor(170, 170, 170))
    p.setColor(QPalette.ColorRole.Highlight,       QColor(80, 80, 80))
    p.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText,
               QColor(100, 100, 100))
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText,
               QColor(100, 100, 100))
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text,
               QColor(100, 100, 100))
    return p


def light_palette() -> QPalette:
    """Palette claire standard."""
    p = QPalette()
    p.setColor(QPalette.ColorRole.Window,          QColor(249, 250, 251))
    p.setColor(QPalette.ColorRole.WindowText,      QColor(17, 24, 39))
    p.setColor(QPalette.ColorRole.Base,            QColor(255, 255, 255))
    p.setColor(QPalette.ColorRole.AlternateBase,   QColor(243, 244, 246))
    p.setColor(QPalette.ColorRole.Text,            QColor(17, 24, 39))
    p.setColor(QPalette.ColorRole.Button,          QColor(255, 255, 255))
    p.setColor(QPalette.ColorRole.ButtonText,      QColor(55, 65, 81))
    p.setColor(QPalette.ColorRole.Link,            QColor(55, 65, 81))
    p.setColor(QPalette.ColorRole.Highlight,       QColor(209, 213, 219))
    p.setColor(QPalette.ColorRole.HighlightedText, QColor(17, 24, 39))
    return p


def apply_theme(theme: str) -> None:
    """Applique le thème à l'application (dark / light / system)."""
    effective = _detect_system_theme() if theme == "system" else theme
    app = QApplication.instance()
    if app is None:
        return
    app.setStyle("Fusion")
    app.setPalette(dark_palette() if effective == "dark" else light_palette())


# ── Feuilles de style sidebar ─────────────────────────────────────────────────

_SIDEBAR_DARK = """
QFrame#sidebar {
    background: #1a1a1a;
    border-right: 1px solid #333333;
}
QLabel#sidebarLogo {
    color: #d4d4d4;
    background: transparent;
}
QLabel#sidebarVersion {
    color: #666666;
    font-size: 11px;
    background: transparent;
}
QPushButton#navButton {
    background: transparent;
    border: none;
    text-align: left;
    padding-left: 20px;
    color: #888888;
    font-size: 13px;
}
QPushButton#navButton:hover {
    color: #d4d4d4;
    background: #252525;
}
QPushButton#navButton:checked {
    color: #e0e0e0;
    background: #3a3a3a;
    border-left: 3px solid #aaaaaa;
    font-weight: bold;
}
"""

_SIDEBAR_LIGHT = """
QFrame#sidebar {
    background: #ffffff;
    border-right: 1px solid #e5e7eb;
}
QLabel#sidebarLogo {
    color: #1f2937;
    background: transparent;
}
QLabel#sidebarVersion {
    color: #9ca3af;
    font-size: 11px;
    background: transparent;
}
QPushButton#navButton {
    background: transparent;
    border: none;
    text-align: left;
    padding-left: 20px;
    color: #6b7280;
    font-size: 13px;
}
QPushButton#navButton:hover {
    color: #111827;
    background: #f3f4f6;
}
QPushButton#navButton:checked {
    color: #111827;
    background: #e5e7eb;
    border-left: 3px solid #6b7280;
    font-weight: bold;
}
"""


# ── Fenêtre principale ────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    """Fenêtre principale avec barre de navigation latérale."""

    def __init__(self, data_dir: Path, tray=None, parent=None):
        super().__init__(parent)
        self._data_dir = data_dir
        self._tray = tray

        self.setWindowTitle("Save My Data")
        self.setMinimumSize(920, 620)
        self.resize(1040, 700)

        self._build_ui()
        self.apply_theme()

    # ── Construction ──────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._sidebar = self._build_sidebar()
        root.addWidget(self._sidebar)

        self._stack = QStackedWidget()
        root.addWidget(self._stack, stretch=1)

        self._pages = {
            "dashboard": DashboardPage(self._data_dir, self._tray),
            "disks":     DisksPage(self._data_dir),
            "settings":  SettingsPage(self._data_dir),
            "restore":   RestorePage(self._data_dir),
            "history":   HistoryPage(self._data_dir),
        }

        for page in self._pages.values():
            self._stack.addWidget(page)

        self._nav_btns["dashboard"].setChecked(True)
        self._stack.setCurrentWidget(self._pages["dashboard"])

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setFixedWidth(210)
        sidebar.setObjectName("sidebar")

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        logo = QLabel("Save My Data")
        logo.setObjectName("sidebarLogo")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        logo.setFont(font)
        logo.setFixedHeight(72)
        layout.addWidget(logo)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setObjectName("sidebarSep")
        layout.addWidget(sep)

        self._nav_btns: dict[str, QPushButton] = {}
        self._btn_group = QButtonGroup(sidebar)
        self._btn_group.setExclusive(True)

        nav_items = [
            ("dashboard", "  Tableau de bord"),
            ("disks",     "  Mes disques"),
            ("settings",  "  Paramètres"),
            ("restore",   "  Restaurer"),
            ("history",   "  Historique"),
        ]

        for key, label in nav_items:
            btn = QPushButton(label)
            btn.setObjectName("navButton")
            btn.setCheckable(True)
            btn.setFixedHeight(50)
            btn.setFlat(True)
            btn.clicked.connect(lambda checked, k=key: self._navigate(k))
            self._nav_btns[key] = btn
            self._btn_group.addButton(btn)
            layout.addWidget(btn)

        layout.addStretch()

        ver = QLabel(f"v{_get_version()}")
        ver.setObjectName("sidebarVersion")
        ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ver.setFixedHeight(36)
        layout.addWidget(ver)

        return sidebar

    # ── Navigation ────────────────────────────────────────────────────────────

    def _navigate(self, key: str) -> None:
        page = self._pages.get(key)
        if page:
            self._stack.setCurrentWidget(page)
            if hasattr(page, "refresh"):
                page.refresh()

    def show_page(self, key: str) -> None:
        """Affiche une page spécifique et lève la fenêtre."""
        btn = self._nav_btns.get(key)
        if btn:
            btn.setChecked(True)
        self._navigate(key)
        self.show()
        self.raise_()
        self.activateWindow()

    # ── Thème ─────────────────────────────────────────────────────────────────

    def apply_theme(self) -> None:
        import config as cfg_module
        theme = cfg_module.get("theme", "dark")
        apply_theme(theme)
        effective = _detect_system_theme() if theme == "system" else theme
        self.setStyleSheet(_SIDEBAR_DARK if effective == "dark" else _SIDEBAR_LIGHT)

    # ── Fermeture ─────────────────────────────────────────────────────────────

    def closeEvent(self, event: QCloseEvent) -> None:
        import config as cfg_module
        behavior = cfg_module.get("ui.close_behavior", "minimize")

        if behavior == "quit":
            event.accept()
            app = QApplication.instance()
            if app:
                app.quit()
        else:
            # Minimiser dans le systray
            event.ignore()
            self.hide()
            if self._tray:
                self._tray.showMessage(
                    "Save My Data",
                    "L'application reste active en arrière-plan.\n"
                    "Double-cliquez sur l'icône pour rouvrir.",
                    self._tray.MessageIcon.Information,
                    3000,
                )
