"""
path_utils.py — Utilitaires de chemin partagés entre les modules core.

Centralise la logique de nommage des sous-dossiers de sauvegarde afin
d'éviter toute divergence entre le moteur de copie et le moteur de restauration.
"""

from pathlib import Path


def target_folder_name(source: Path) -> str:
    """
    Génère le nom du sous-dossier cible pour un disque/dossier source.

    C:\\         →  [C]
    D:\\         →  [D]
    D:\\Photos   →  [Photos]
    /home/user   →  [user]
    """
    drive = source.drive  # 'C:' sur Windows, '' sur Unix
    if drive:
        try:
            if source == source.parent:
                return f"[{drive.rstrip(':')}]"
        except Exception:
            pass
    return f"[{source.name}]" if source.name else "[backup]"
