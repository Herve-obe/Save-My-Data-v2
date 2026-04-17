# Save My Data

Logiciel de sauvegarde automatique et incrémentale pour Windows. Tourne discrètement dans le systray et copie uniquement les fichiers nouveaux ou modifiés.

## Fonctionnalités

- **Sauvegarde incrémentale** — comparaison par hash xxHash (xxh3), seuls les fichiers nouveaux ou modifiés sont copiés
- **Deux modes** — sauvegarde à l'extinction de l'ordinateur et/ou à heure fixe chaque jour
- **Écriture atomique** — aucun fichier corrompu en cas de coupure de courant (copie via fichier temporaire `.smd_tmp` + renommage atomique)
- **Restauration** — depuis l'interface ou le menu clic droit de l'Explorateur Windows
- **Gestion des orphelins** — les fichiers supprimés de la source restent dans la sauvegarde ; l'application demande quoi en faire au prochain démarrage
- **Historique** — journal complet de chaque sauvegarde (date, fichiers copiés, inchangés, erreurs, durée)
- **Filtres** — exclure des extensions (`.tmp`, `.log`…), des dossiers (`node_modules`, `.git`…) et limiter la taille par fichier
- **Alerte espace disque** — notification systray si le disque cible passe sous 10 % d'espace libre
- **Interface** — thème sombre / clair / système, sidebar de navigation

## Installation

1. Téléchargez `SaveMyData-v1.2.0-Windows.zip` depuis la [page Releases](https://github.com/Herve-obe/Save-My-Data-v2/releases)
2. Extrayez le dossier à l'emplacement de votre choix
3. Lancez `SaveMyData.exe`
4. Allez dans **Mes disques** pour choisir votre disque de sauvegarde et vos sources
5. Configurez le mode de sauvegarde dans **Paramètres**

## Utilisation

L'application se minimise dans le systray après fermeture de la fenêtre. Double-cliquez sur l'icône pour rouvrir.

**Clic droit sur l'icône systray :**
- Lancer une sauvegarde maintenant
- Restaurer un fichier
- Réviser les fichiers orphelins
- Quitter

**Restauration depuis l'Explorateur Windows :**
Activez le menu contextuel dans *Paramètres → Intégration Windows*, puis faites un clic droit sur n'importe quel fichier et choisissez *Restaurer depuis le dernier back-up*.

## Développement

**Prérequis :**
```
Python 3.12+
pip install -r requirements.txt
```

**Lancer en développement :**
```
cd src
python main.py
```

**Compiler l'exe :**
```
build.bat
```
Sortie : `dist\SaveMyData\SaveMyData.exe`

**Modes CLI :**
```
python main.py backup <source> <cible>   # sauvegarde manuelle
python main.py orphans                   # révision des orphelins
```

## Stack technique

| Composant | Rôle |
|---|---|
| Python 3.12 + PySide6 | Interface graphique (Qt6) |
| xxhash (xxh3) | Comparaison bit-à-bit ultra-rapide |
| APScheduler | Sauvegarde planifiée à heure fixe |
| psutil | Informations et espace disques |
| send2trash | Envoi à la Corbeille avant restauration |
| PyInstaller | Compilation en `.exe` autonome |

## Licence

MIT — voir [LICENSE](LICENSE)
