"""
registry_manager.py — Intégration du menu contextuel Windows via le registre.

Enregistre l'entrée "Restaurer depuis le dernier back-up" dans le menu
contextuel de l'Explorateur Windows pour les fichiers et les dossiers.

Utilise HKEY_CURRENT_USER (pas d'administrateur requis).

Clés créées :
    HKCU\\Software\\Classes\\*\\shell\\SaveMyDataRestore\\
    HKCU\\Software\\Classes\\*\\shell\\SaveMyDataRestore\\command\\
    HKCU\\Software\\Classes\\Directory\\shell\\SaveMyDataRestore\\
    HKCU\\Software\\Classes\\Directory\\shell\\SaveMyDataRestore\\command\\
"""

import sys
from pathlib import Path

VERB_NAME  = "SaveMyDataRestore"
VERB_LABEL = "Restaurer depuis le dernier back-up"
HKCU_CLASSES = r"Software\Classes"

# Clés pour les fichiers et les dossiers
_SHELL_KEYS = [
    rf"{HKCU_CLASSES}\*\shell\{VERB_NAME}",
    rf"{HKCU_CLASSES}\Directory\shell\{VERB_NAME}",
]


def register(python_exe: Path, main_script: Path) -> tuple[bool, str]:
    """
    Enregistre le menu contextuel "Restaurer depuis le dernier back-up".

    Args:
        python_exe:  Chemin vers l'exécutable Python (sys.executable).
        main_script: Chemin vers src/main.py.

    Returns:
        (succès: bool, message: str)
    """
    if sys.platform != "win32":
        return False, "Menu contextuel uniquement disponible sur Windows."

    import winreg

    # Commande appelée par Windows lors du clic droit.
    # En mode frozen (.exe), python_exe est le .exe → pas besoin du script.
    # Les guillemets autour de %1 gèrent les chemins avec espaces.
    if getattr(sys, "frozen", False):
        command = f'"{python_exe}" --restore "%1"'
    else:
        command = f'"{python_exe}" -X utf8 "{main_script}" --restore "%1"'

    try:
        for shell_key in _SHELL_KEYS:
            # Clé principale : libellé du menu
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, shell_key) as key:
                winreg.SetValueEx(key, "",    0, winreg.REG_SZ, VERB_LABEL)
                winreg.SetValueEx(key, "Icon", 0, winreg.REG_SZ, str(python_exe))

            # Sous-clé command : commande à exécuter
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"{shell_key}\command") as key:
                winreg.SetValueEx(key, "", 0, winreg.REG_SZ, command)

        return True, "Menu contextuel enregistré avec succès."

    except PermissionError:
        return False, "Permission refusée lors de l'écriture dans le registre."
    except Exception as exc:
        return False, f"Erreur inattendue : {exc}"


def unregister() -> tuple[bool, str]:
    """
    Supprime les entrées de menu contextuel du registre.

    Returns:
        (succès: bool, message: str)
    """
    if sys.platform != "win32":
        return False, "Windows uniquement."

    import winreg

    try:
        for shell_key in _SHELL_KEYS:
            for subkey in [rf"{shell_key}\command", shell_key]:
                try:
                    winreg.DeleteKey(winreg.HKEY_CURRENT_USER, subkey)
                except FileNotFoundError:
                    pass  # Déjà supprimée

        return True, "Menu contextuel supprimé."

    except Exception as exc:
        return False, f"Erreur : {exc}"


def is_registered() -> bool:
    """Retourne True si le menu contextuel est déjà enregistré."""
    if sys.platform != "win32":
        return False

    import winreg

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            rf"{HKCU_CLASSES}\*\shell\{VERB_NAME}",
        ):
            return True
    except FileNotFoundError:
        return False
