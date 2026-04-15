"""
path_utils.py — Utilitaires de chemin partagés entre les modules core.

Centralise la logique de nommage des sous-dossiers de sauvegarde afin
d'éviter toute divergence entre le moteur de copie et le moteur de restauration.
"""

from pathlib import Path


def target_folder_name(source: Path) -> str:
    """
    Génère le nom du sous-dossier cible pour un disque/dossier source.

    La lettre de lecteur est incluse pour les sous-dossiers afin d'éviter
    les collisions quand deux disques différents ont un sous-dossier de même nom.

    Exemples :
        C:\\         →  [C]
        D:\\         →  [D]
        D:\\Photos   →  [D_Photos]      ← lettre de lecteur préfixée
        C:\\Photos   →  [C_Photos]      ← pas de collision avec D:\\Photos
        /home/user  →  [user]
    """
    drive = source.drive  # 'C:' sur Windows, '' sur Unix

    if drive:
        drive_letter = drive.rstrip(":")
        # Racine du lecteur : C:\\ → [C], D:\\ → [D]
        if source == source.parent:
            return f"[{drive_letter}]"
        # Sous-dossier : inclure la lettre de lecteur pour éviter les collisions
        # D:\\Photos → [D_Photos], C:\\Photos → [C_Photos]
        return f"[{drive_letter}_{source.name}]" if source.name else f"[{drive_letter}]"

    # Chemin Unix : /home/user → [user]
    return f"[{source.name}]" if source.name else "[backup]"
