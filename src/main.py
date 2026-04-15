"""
main.py — Point d'entrée de Save My Data.

Modes de lancement :
    python main.py                        → GUI (systray + shutdown handler)
    python main.py backup <src> <cible>   → CLI : sauvegarde manuelle
    python main.py orphans                → CLI : révision des fichiers orphelins
    python main.py --restore <chemin>     → Restaurer un fichier (depuis clic droit)
"""

import sys
import argparse
from pathlib import Path

# Force UTF-8 pour l'affichage correct des accents dans le terminal Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Ajoute le dossier src au path pour les imports
sys.path.insert(0, str(Path(__file__).parent))

import config
from core.copy_engine import run_backup
from core.orphan_manager import OrphanManager

# En mode frozen (.exe) : %APPDATA%/SaveMyData/data
# En développement      : <racine_projet>/data
DATA_DIR = config.app_base_dir() / "data"

# Référence aux workers systray actifs pour éviter le garbage collection
_active_workers: list = []


# ══════════════════════════════════════════════════════════════════════════════
# MODE GUI — Application systray avec shutdown handler
# ══════════════════════════════════════════════════════════════════════════════

def launch_gui(autostart: bool = False) -> None:
    """
    Lance l'application en mode GUI.

    autostart=False (lancement manuel) → ouvre la fenêtre principale immédiatement.
    autostart=True  (démarrage Windows) → démarre silencieusement dans le systray.
    """
    from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
    from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QAction
    from PySide6.QtCore import Qt, QTimer

    app = QApplication(sys.argv)
    app.setApplicationName("Save My Data")
    app.setOrganizationName("SaveMyData")
    app.setQuitOnLastWindowClosed(False)  # Reste actif en systray

    # Répertoire de données : dossier data/ du projet (migration vers AppData en M7)
    app_data_dir = DATA_DIR
    app_data_dir.mkdir(parents=True, exist_ok=True)

    # ── Appliquer le thème Fusion + palette ───────────────────────────────────
    from ui.main_window import apply_theme
    apply_theme(config.get("theme", "dark"))

    # ── Auto-enregistrement du menu contextuel clic droit ─────────────────────
    # Enregistré automatiquement si la config l'autorise et qu'il ne l'est pas déjà
    if config.get("restore.context_menu", True):
        from core.registry_manager import is_registered, register as _reg_ctx
        if not is_registered():
            _reg_ctx(Path(sys.executable), Path(__file__).resolve())

    # ── Shutdown handler ──────────────────────────────────────────────────────
    app.commitDataRequest.connect(
        lambda sm: _handle_shutdown(sm, app, app_data_dir)
    )

    # ── Icône systray ─────────────────────────────────────────────────────────
    icon = _create_icon()
    tray = QSystemTrayIcon(icon, app)
    tray.setToolTip("Save My Data — Prêt")

    # ── Planificateur de sauvegardes ──────────────────────────────────────────
    from core.scheduler_manager import SchedulerManager
    scheduler = SchedulerManager(tray, app_data_dir)
    scheduler.start()
    app.aboutToQuit.connect(scheduler.stop)

    # ── Fenêtre principale ────────────────────────────────────────────────────
    from ui.main_window import MainWindow
    main_window = MainWindow(app_data_dir, tray=tray)

    # Replanifier dès que les paramètres sont enregistrés
    main_window._pages["settings"].settings_saved.connect(scheduler.reschedule)

    # Double-clic sur l'icône systray → afficher/masquer la fenêtre
    def _on_tray_activated(reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            if main_window.isVisible():
                main_window.hide()
            else:
                main_window.show()
                main_window.raise_()
                main_window.activateWindow()

    tray.activated.connect(_on_tray_activated)

    # ── Menu systray ──────────────────────────────────────────────────────────
    menu = QMenu()

    action_open = QAction("Ouvrir Save My Data", menu)
    action_open.triggered.connect(lambda: (
        main_window.show(), main_window.raise_(), main_window.activateWindow()
    ))
    menu.addAction(action_open)

    menu.addSeparator()

    action_backup = QAction("Lancer une sauvegarde maintenant", menu)
    action_backup.triggered.connect(lambda: _run_manual_backup(tray, app_data_dir))
    menu.addAction(action_backup)

    action_restore = QAction("Restaurer un fichier...", menu)
    action_restore.triggered.connect(lambda: _open_restore_picker(app_data_dir))
    menu.addAction(action_restore)

    # Action orphelins (texte mis à jour dynamiquement selon le nombre en attente)
    action_orphans = QAction("Réviser les fichiers orphelins", menu)
    action_orphans.triggered.connect(lambda: _open_orphan_review(app_data_dir))
    menu.addAction(action_orphans)

    menu.addSeparator()

    # Activer/désactiver le menu contextuel Windows (clic droit Explorateur)
    from core.registry_manager import is_registered
    _ctx_label = ("Désactiver le clic droit Explorateur"
                  if is_registered() else "Activer le clic droit Explorateur")
    action_ctx = QAction(_ctx_label, menu)
    action_ctx.triggered.connect(lambda: _toggle_context_menu(action_ctx))
    menu.addAction(action_ctx)

    menu.addSeparator()

    action_quit = QAction("Quitter Save My Data", menu)
    action_quit.triggered.connect(app.quit)
    menu.addAction(action_quit)

    tray.setContextMenu(menu)
    tray.show()

    # ── Afficher la fenêtre principale si lancement manuel ────────────────────
    if not autostart:
        main_window.show()

    # ── Vérification des orphelins au démarrage (après 1s) ────────────────────
    def _check_orphans_on_start() -> None:
        manager = OrphanManager(app_data_dir)
        n = manager.count_pending()
        if n > 0:
            s = "s" if n > 1 else ""
            action_orphans.setText(f"Réviser les fichiers orphelins ({n})")
            tray.setToolTip(f"Save My Data — {n} fichier{s} à réviser")
            tray.showMessage(
                "Save My Data — Action requise",
                f"{n} fichier{s} orphelin{s} attendant votre décision.\n"
                "Clic droit sur l'icône → Réviser les fichiers orphelins",
                QSystemTrayIcon.MessageIcon.Warning,
                6000,
            )
        else:
            tray.showMessage(
                "Save My Data",
                "Actif en arrière-plan. Double-cliquez sur l'icône pour ouvrir.",
                QSystemTrayIcon.MessageIcon.Information,
                3000,
            )

    QTimer.singleShot(1000, _check_orphans_on_start)

    sys.exit(app.exec())


def _handle_shutdown(session_manager, app, data_dir: Path) -> None:
    """
    Intercepte l'événement d'extinction de l'OS.
    Appelé par Qt via le signal commitDataRequest.
    """
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    cfg = config.load()
    mode = cfg.get('backup', {}).get('mode', 'shutdown')

    # Si la sauvegarde à l'extinction n'est pas activée → laisser passer
    if mode not in ('shutdown', 'both'):
        return

    target_str = cfg.get('backup', {}).get('target_disk', '')
    source_strs = cfg.get('backup', {}).get('source_disks', [])

    # Si pas de disques configurés → laisser passer
    if not target_str or not source_strs:
        return

    target = Path(target_str)
    sources = [Path(s) for s in source_strs]

    # Vérifier que le disque cible est accessible
    if not target.exists():
        _show_disk_missing(target, session_manager, app, data_dir, sources, cfg)
        return

    # Bloquer l'extinction et lancer la sauvegarde
    session_manager.cancel()
    _start_shutdown_backup(sources, target, cfg, data_dir, app)


def _show_disk_missing(
    target: Path, session_manager, app, data_dir: Path,
    sources: list[Path], cfg: dict,
) -> None:
    """Affiche l'alerte 'Disque introuvable' et gère le choix utilisateur."""
    from PySide6.QtCore import QTimer
    from ui.disk_missing_dialog import DiskMissingDialog

    while True:
        dialog = DiskMissingDialog(target)
        dialog.exec()
        choice = dialog.chosen()

        if choice == DiskMissingDialog.RETRY:
            if target.exists():
                # Disque branché — on peut lancer la sauvegarde
                session_manager.cancel()
                _start_shutdown_backup(sources, target, cfg, data_dir, app)
                return
            else:
                continue  # Réafficher le dialog

        elif choice == DiskMissingDialog.CANCEL_SHUTDOWN:
            session_manager.cancel()
            return  # Annule l'extinction, l'app reste ouverte

        else:  # SHUTDOWN_ANYWAY
            return  # Laisse l'extinction se dérouler sans sauvegarde


def _start_shutdown_backup(
    sources: list[Path], target: Path, cfg: dict,
    data_dir: Path, app,
) -> None:
    """Affiche la fenêtre de progression et lance le BackupWorker."""
    from PySide6.QtCore import QTimer
    from core.backup_worker import BackupWorker, write_last_backup
    from ui.shutdown_progress import ShutdownProgressDialog

    filters = cfg.get('filters', {})

    # Fenêtre de progression
    dialog = ShutdownProgressDialog()
    dialog.show()

    # Worker de sauvegarde
    worker = BackupWorker(sources, target, filters, data_dir)
    _active_workers.append(worker)  # Empêche le GC pendant l'exécution

    # Connexions signaux → slots
    worker.disk_started.connect(dialog.on_disk_started)
    worker.progress.connect(dialog.on_progress)
    worker.error.connect(
        lambda msg: dialog._disk_label.setText(f"Erreur : {msg}")
    )

    def on_backup_done(report) -> None:
        if worker in _active_workers:
            _active_workers.remove(worker)
        if not report.cancelled:
            write_last_backup(data_dir, report)
        dialog.on_finished(report.total_copied, report.total_errors)
        # Laisser 2 secondes pour que l'utilisateur voie le résultat
        QTimer.singleShot(2000, app.quit)

    worker.finished.connect(on_backup_done)

    # Annulation demandée par l'utilisateur → stopper le worker et quitter
    dialog.abort_requested.connect(worker.cancel)
    dialog.abort_requested.connect(lambda: QTimer.singleShot(500, app.quit))

    worker.start()


def _run_manual_backup(tray, data_dir: Path) -> None:
    """Déclenche une sauvegarde manuelle depuis le menu systray."""
    from PySide6.QtWidgets import QSystemTrayIcon
    from core.backup_worker import BackupWorker, write_last_backup

    cfg = config.load()
    target_str = cfg.get('backup', {}).get('target_disk', '')
    source_strs = cfg.get('backup', {}).get('source_disks', [])
    filters = cfg.get('filters', {})

    if not target_str or not source_strs:
        tray.showMessage(
            "Save My Data",
            "Aucun disque configuré. Ouvrez les Paramètres.",
            QSystemTrayIcon.MessageIcon.Warning, 4000,
        )
        return

    target = Path(target_str)
    sources = [Path(s) for s in source_strs]

    tray.showMessage(
        "Save My Data",
        "Sauvegarde en cours...",
        QSystemTrayIcon.MessageIcon.Information, 2000,
    )

    worker = BackupWorker(sources, target, filters, data_dir)
    _active_workers.append(worker)  # Empêche le GC pendant l'exécution

    def on_done(report):
        if worker in _active_workers:
            _active_workers.remove(worker)
        write_last_backup(data_dir, report)
        n_orphans = len(report.all_orphans)
        msg = f"Sauvegarde terminée — {report.total_copied} fichier(s) copié(s)."
        if n_orphans:
            msg += f"\n{n_orphans} fichier(s) orphelin(s) à réviser."
        tray.showMessage(
            "Save My Data",
            msg,
            QSystemTrayIcon.MessageIcon.Information, 5000,
        )

    worker.finished.connect(on_done)
    worker.start()


def _open_restore_picker(data_dir: Path) -> None:
    """Ouvre un sélecteur de fichier puis le dialogue de restauration."""
    from PySide6.QtWidgets import QFileDialog
    from core.restore_engine import find_backup
    from ui.restore_dialog import RestoreDialog, NotFoundDialog

    cfg = config.load()
    target_str  = cfg.get('backup', {}).get('target_disk', '')
    source_strs = cfg.get('backup', {}).get('source_disks', [])

    if not target_str or not source_strs:
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.warning(None, "Save My Data",
                            "Aucun disque configuré. Configurez d'abord votre sauvegarde.")
        return

    path_str, _ = QFileDialog.getOpenFileName(None, "Sélectionner un fichier à restaurer")
    if not path_str:
        return

    source_path  = Path(path_str)
    source_disks = [Path(s) for s in source_strs]
    target_disk  = Path(target_str)

    candidate = find_backup(source_path, source_disks, target_disk)
    if candidate is None:
        NotFoundDialog(source_path).exec()
        return

    RestoreDialog(candidate).exec()


def _toggle_context_menu(action) -> None:
    """Active ou désactive le menu contextuel Windows (clic droit Explorateur)."""
    import sys
    from PySide6.QtWidgets import QMessageBox
    from core.registry_manager import register, unregister, is_registered

    if is_registered():
        ok, msg = unregister()
        label = "Activer le clic droit Explorateur"
    else:
        python_exe  = Path(sys.executable)
        main_script = Path(__file__).resolve()
        ok, msg = register(python_exe, main_script)
        label = "Désactiver le clic droit Explorateur"

    if ok:
        action.setText(label)
        QMessageBox.information(None, "Save My Data", msg)
    else:
        QMessageBox.warning(None, "Save My Data", f"Échec : {msg}")


def _open_orphan_review(data_dir: Path) -> None:
    """Ouvre la fenêtre de révision des fichiers orphelins."""
    from ui.orphan_review_dialog import OrphanReviewDialog

    manager = OrphanManager(data_dir)
    pending = manager.pending

    if not pending:
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(
            None,
            "Save My Data",
            "Aucun fichier orphelin en attente de révision.",
        )
        return

    dialog = OrphanReviewDialog(pending, data_dir)
    dialog.exec()


def _create_icon():
    """Crée une icône simple pour le systray (sera remplacée en M5)."""
    from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont
    from PySide6.QtCore import Qt

    size = 32
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Cercle bleu
    painter.setBrush(QColor("#1565C0"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(1, 1, size - 2, size - 2)

    # Lettre "S"
    painter.setPen(QColor("white"))
    font = QFont()
    font.setPixelSize(18)
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "S")

    painter.end()
    return QIcon(pixmap)


# ══════════════════════════════════════════════════════════════════════════════
# MODE CLI — Sauvegarde et révision des orphelins en ligne de commande
# ══════════════════════════════════════════════════════════════════════════════

def cmd_backup(args: argparse.Namespace) -> None:
    source = Path(args.source)
    target = Path(args.target)

    if not source.exists():
        print(f"Erreur : dossier source introuvable : {source}")
        sys.exit(1)

    print(f"\nSave My Data — Sauvegarde")
    print(f"  Source : {source}")
    print(f"  Cible  : {target}")
    print(f"\nScan en cours...\n")

    def progress(done: int, total: int, filename: str) -> None:
        if total == 0:
            return
        pct = int(done / total * 100)
        bar = "#" * (pct // 5) + "-" * (20 - pct // 5)
        short = filename[-55:] if len(filename) > 55 else filename
        print(f"\r  [{bar}] {pct:3d}%  {short:<55}", end="", flush=True)

    cfg_filters = config.load().get("filters", {})
    report = run_backup(
        source_root=source,
        target_root=target,
        excluded_extensions=cfg_filters.get("excluded_extensions", []),
        excluded_folders=cfg_filters.get("excluded_folders", []),
        max_size_bytes=cfg_filters.get("max_size_bytes", 0),
        progress_callback=progress,
    )

    print(f"\n\n{'-' * 50}")
    print(report.summary())
    print('-' * 50)

    if report.orphan_paths:
        manager = OrphanManager(DATA_DIR)
        added = manager.add_orphans(report.orphan_paths, source, target)
        if added:
            print(f"\n[!] {added} fichier(s) orphelin(s) enregistre(s).")
            print(f"    Lance 'python main.py orphans' pour les reviser.")

    if report.errors:
        print(f"\nErreurs ({len(report.errors)}) :")
        for path, err in report.errors:
            print(f"  x  {path}")
            print(f"     {err}")


def cmd_orphans(_args: argparse.Namespace) -> None:
    manager = OrphanManager(DATA_DIR)
    pending = manager.pending

    if not pending:
        print("\nAucun fichier orphelin en attente de révision.")
        return

    print(f"\n{len(pending)} fichier(s) orphelin(s) a reviser :\n")

    for i, entry in enumerate(pending, 1):
        size_kb = entry.size / 1024
        print(f"  [{i:3d}]  {entry.source_path}")
        print(f"         Sauvegarde : {entry.target_path}")
        print(f"         Detecte le : {entry.detected_at[:10]}  |  Taille : {size_kb:.1f} Ko")
        print()

    print("Actions : k=Conserver  d=Supprimer  ka=Conserver tout  da=Supprimer tout  q=Quitter\n")

    for entry in list(pending):
        print(f"  {entry.source_path}")
        choice = input("  Action [k/d/ka/da/q] : ").strip().lower()

        if choice == 'q':
            print("\nAucune modification.")
            return
        elif choice == 'k':
            manager.apply_action(entry.target_path, "keep")
            print("  -> Conserve.\n")
        elif choice == 'd':
            ok, msg = manager.apply_action(entry.target_path, "delete")
            print(f"  -> {'Supprime.' if ok else f'Erreur : {msg}'}\n")
        elif choice == 'ka':
            ok, ko = manager.apply_action_all("keep")
            print(f"\n  -> {ok} conserve(s), {ko} erreur(s).")
            return
        elif choice == 'da':
            ok, ko = manager.apply_action_all("delete")
            print(f"\n  -> {ok} supprime(s), {ko} erreur(s).")
            return
        else:
            manager.apply_action(entry.target_path, "keep")
            print("  -> Conserve (choix non reconnu).\n")

    manager.clear_resolved()
    print("Revision terminee.")


# ══════════════════════════════════════════════════════════════════════════════
# POINT D'ENTRÉE
# ══════════════════════════════════════════════════════════════════════════════

def launch_restore_mode(paths: list[str]) -> None:
    """
    Mode restauration : lancé par le clic droit dans l'Explorateur Windows.
    Affiche le dialogue de confirmation et restaure le(s) fichier(s).
    """
    from PySide6.QtWidgets import QApplication
    from core.restore_engine import find_backup
    from ui.restore_dialog import RestoreDialog, NotFoundDialog

    app = QApplication(sys.argv)
    app.setApplicationName("Save My Data")
    app.setQuitOnLastWindowClosed(True)

    cfg = config.load()
    target_str  = cfg.get('backup', {}).get('target_disk', '')
    source_strs = cfg.get('backup', {}).get('source_disks', [])

    if not target_str or not source_strs:
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.warning(None, "Save My Data",
                            "Aucun disque de sauvegarde configuré.")
        sys.exit(1)

    source_disks = [Path(s) for s in source_strs]
    target_disk  = Path(target_str)

    shown = False
    for path_str in paths:
        source_path = Path(path_str)
        candidate   = find_backup(source_path, source_disks, target_disk)

        if candidate is None:
            NotFoundDialog(source_path).exec()
        else:
            RestoreDialog(candidate).exec()
            shown = True

    sys.exit(0)


def main() -> None:
    # ── Détection du mode --restore (appelé par clic droit Explorateur) ───────
    if "--restore" in sys.argv:
        idx   = sys.argv.index("--restore")
        paths = sys.argv[idx + 1:]
        if paths:
            launch_restore_mode(paths)
            return

    # ── Démarrage automatique Windows : --autostart → systray seul, pas de fenêtre
    _autostart = "--autostart" in sys.argv
    if _autostart:
        sys.argv = [a for a in sys.argv if a != "--autostart"]

    # ── Parser CLI standard ───────────────────────────────────────────────────
    parser = argparse.ArgumentParser(
        prog="save-my-data",
        description="Save My Data — Sauvegarde automatique cross-plateforme",
    )
    sub = parser.add_subparsers(dest="command")

    bp = sub.add_parser("backup", help="Lancer une sauvegarde manuelle (CLI)")
    bp.add_argument("source", help="Dossier ou disque source")
    bp.add_argument("target", help="Dossier cible dans le disque de sauvegarde")

    sub.add_parser("orphans", help="Réviser les fichiers orphelins (CLI)")

    args = parser.parse_args()

    if args.command == "backup":
        cmd_backup(args)
    elif args.command == "orphans":
        cmd_orphans(args)
    else:
        launch_gui(autostart=_autostart)


if __name__ == "__main__":
    main()
