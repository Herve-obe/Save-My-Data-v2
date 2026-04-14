"""
orphan_manager.py — Suivi des fichiers supprimés de la source mais conservés sur la cible.

Un fichier est "orphelin" quand il est présent dans la sauvegarde mais n'existe
plus sur le disque source. Le logiciel ne supprime jamais automatiquement ces
fichiers : il demande à l'utilisateur quoi faire au prochain démarrage.

Les décisions en attente sont persistées dans data/orphans.json.
"""

import json
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Literal


ORPHAN_DB = "orphans.json"


@dataclass
class OrphanEntry:
    """Représente un fichier orphelin en attente de décision."""
    target_path: str            # Chemin absolu sur le disque cible
    source_path: str            # Chemin d'origine sur le disque source (reconstitué)
    detected_at: str            # Date ISO de détection
    size: int = 0               # Taille en octets
    action: Literal["pending", "keep", "delete"] = "pending"


class OrphanManager:
    """
    Gère la liste des fichiers orphelins.

    Usage :
        manager = OrphanManager(data_dir)
        manager.add_orphans(orphan_paths, source_root, target_root)
        for entry in manager.pending:
            print(entry.source_path, entry.size)
        manager.apply_action(entry.target_path, "delete")
    """

    def __init__(self, data_dir: Path):
        self._db_path = data_dir / ORPHAN_DB
        self._entries: list[OrphanEntry] = []
        self._load()

    # ── Persistance ──────────────────────────────────────────────────────────

    def _load(self) -> None:
        if not self._db_path.exists():
            return
        try:
            raw = json.loads(self._db_path.read_text(encoding='utf-8'))
            self._entries = [OrphanEntry(**item) for item in raw]
        except (json.JSONDecodeError, TypeError, KeyError):
            self._entries = []

    def _save(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db_path.write_text(
            json.dumps([asdict(e) for e in self._entries], ensure_ascii=False, indent=2),
            encoding='utf-8',
        )

    # ── Ajout ────────────────────────────────────────────────────────────────

    def add_orphans(
        self,
        orphan_paths: list[Path],
        source_root: Path,
        target_root: Path,
    ) -> int:
        """
        Enregistre les nouveaux orphelins détectés lors d'une sauvegarde.
        Les chemins déjà connus sont ignorés.

        Returns:
            Nombre de nouveaux orphelins ajoutés.
        """
        existing = {e.target_path for e in self._entries}
        added = 0

        for path in orphan_paths:
            key = str(path)
            if key in existing:
                continue

            # Reconstituer le chemin source d'origine
            try:
                rel = path.relative_to(target_root)
                original = str(source_root / rel)
            except ValueError:
                original = "inconnu"

            try:
                size = path.stat().st_size
            except OSError:
                size = 0

            self._entries.append(OrphanEntry(
                target_path=key,
                source_path=original,
                detected_at=datetime.now().isoformat(),
                size=size,
            ))
            added += 1

        if added > 0:
            self._save()

        return added

    # ── Consultation ─────────────────────────────────────────────────────────

    @property
    def pending(self) -> list[OrphanEntry]:
        """Retourne les orphelins en attente de décision."""
        return [e for e in self._entries if e.action == "pending"]

    @property
    def all_entries(self) -> list[OrphanEntry]:
        return list(self._entries)

    def count_pending(self) -> int:
        return len(self.pending)

    # ── Actions utilisateur ──────────────────────────────────────────────────

    def _apply_single(
        self,
        entry: "OrphanEntry",
        action: Literal["keep", "delete"],
    ) -> tuple[bool, str]:
        """
        Applique une action sur un orphelin sans persister (appel interne).
        Utilisé par apply_action et apply_action_all pour éviter N sauvegardes.
        """
        entry.action = action
        if action == "delete":
            try:
                Path(entry.target_path).unlink(missing_ok=True)
            except OSError as e:
                entry.action = "pending"   # Remet en attente si échec
                return False, f"Impossible de supprimer : {e}"
        return True, "OK"

    def apply_action(
        self,
        target_path: str,
        action: Literal["keep", "delete"],
    ) -> tuple[bool, str]:
        """
        Applique la décision de l'utilisateur pour un orphelin et sauvegarde.

        Args:
            target_path: Chemin absolu du fichier sur le disque cible.
            action:      "keep" (conserver) ou "delete" (supprimer de la sauvegarde).

        Returns:
            (succès: bool, message: str)
        """
        for entry in self._entries:
            if entry.target_path == target_path:
                ok, msg = self._apply_single(entry, action)
                self._save()
                return ok, msg
        return False, "Orphelin introuvable."

    def apply_action_all(self, action: Literal["keep", "delete"]) -> tuple[int, int]:
        """
        Applique la même action à tous les orphelins en attente.
        Effectue une seule écriture disque (vs N dans l'ancienne implémentation).

        Returns:
            (succès, échecs)
        """
        ok = 0
        ko = 0
        for entry in list(self.pending):   # snapshot avant modification
            success, _ = self._apply_single(entry, action)
            if success:
                ok += 1
            else:
                ko += 1
        self._save()   # Un seul accès disque pour tout le lot
        return ok, ko

    def clear_resolved(self) -> None:
        """
        Nettoie la liste après révision.

        Conserve les entrées "keep" : elles servent de mémoire pour ne pas
        re-signaler les mêmes fichiers à la prochaine sauvegarde.
        Supprime uniquement les entrées "delete" (fichiers déjà effacés).
        """
        self._entries = [e for e in self._entries if e.action != "delete"]
        self._save()
