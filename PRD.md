# PRD — Save My Data
## Logiciel de back-up automatique cross-plateforme

**Version :** 0.3
**Date :** 2026-04-14
**Repo :** https://github.com/Herve-obe/Save-My-Data
**Licence :** Open-source (MIT)

---

## 1. Contexte & Problème

La perte de données est un risque courant : disque défaillant, mauvaise manipulation, ransomware.
Les solutions existantes (Time Machine, robocopy, rsync scripts) sont soit trop liées à un OS, soit trop techniques pour un usage quotidien.

**Save My Data** offre un back-up automatique fiable, configurable et simple d'usage, fonctionnant sur Windows, macOS et Linux depuis une seule base de code. Il est destiné à tout public, y compris les personnes non initiées à l'informatique.

---

## 2. Concept Central

L'utilisateur dispose de plusieurs disques (internes et externes) et d'un disque de sauvegarde désigné (ex. : disque "Back-Up" de 10 To).

Le logiciel surveille les disques sources sélectionnés, compare leur contenu à la sauvegarde existante via **xxHash** (comparaison bit-à-bit ultra-rapide), et ne copie que les fichiers **nouveaux ou modifiés**.

---

## 3. Objectifs Produit

| Objectif | Indicateur de succès |
|---|---|
| Back-up automatique sans intervention | Les sauvegardes se déclenchent selon le mode choisi |
| Cross-plateforme | Fonctionne identiquement sur Windows, macOS, Linux |
| Interface claire pour tous | Un non-technicien configure une sauvegarde en < 5 min |
| Fiabilité bit-à-bit | Aucune corruption silencieuse — xxHash sur chaque fichier |
| Performances | Impact CPU/RAM < 5 % en tâche de fond |
| Open-source | Licence MIT, code public sur GitHub |

---

## 4. Utilisateurs Cibles

- **Particulier** : sauvegarde de documents, photos, projets perso
- **Développeur** : sauvegarde de repos locaux, configs, clés
- **PME / Indépendant** : rotation de sauvegardes sur disque dédié

---

## 5. Fonctionnalités

### 5.1 Démarrage & Cycle de Vie

- **Démarrage automatique au boot** (option activable/désactivable dans les Paramètres)
- Le logiciel s'exécute en **icône systray** (barre des tâches) — discret, toujours disponible
- Double-clic sur l'icône systray ouvre l'interface principale

### 5.2 Disques Sources & Disque Cible

- Sélection de **un ou plusieurs disques sources** (internes et/ou externes)
- Désignation d'un **disque cible unique** (ex. : "Back-Up" 10 To)
- Sur le disque cible, création automatique d'un **dossier dédié par disque source** :
  ```
  Back-Up:\
  ├── [Disque_C]\        ← miroir du disque C:
  ├── [Disque_D]\        ← miroir du disque D:
  └── [Disque_Photos]\   ← miroir du disque externe Photos
  ```
- La sauvegarde couvre **l'intégralité du disque source** (tous les fichiers, sans filtre système implicite)
- Filtres d'exclusion configurables par l'utilisateur (extensions, dossiers, taille)

### 5.3 Comparaison & Copie (Moteur Principal)

- Comparaison **bit-à-bit via xxHash (xxh3)** — plus rapide que MD5/SHA et aussi fiable
- Algorithme de décision par fichier :
  ```
  Fichier présent sur source ET cible ?
    → Hash identique   → Rien à faire
    → Hash différent   → Remplacer sur la cible (fichier modifié)
  Fichier présent sur source UNIQUEMENT ?
    → Copier vers la cible (nouveau fichier)
  Fichier présent sur cible UNIQUEMENT (supprimé de la source) ?
    → Conserver sur la cible + mémoriser pour alerte au prochain démarrage
  ```
- Rapport de copie horodaté après chaque sauvegarde (fichiers copiés, erreurs, durée, taille)

### 5.4 Gestion des Fichiers Supprimés

- Un fichier supprimé de la source est **conservé sur le disque cible** (pas de suppression automatique)
- Au prochain démarrage du logiciel, une **fenêtre de révision** s'affiche listant tous les fichiers orphelins :
  - Nom, chemin d'origine, date de suppression détectée, taille
  - Actions disponibles par fichier : **Supprimer de la sauvegarde** | **Conserver** | **Restaurer sur la source**
  - Actions globales : "Supprimer tout" | "Conserver tout"

### 5.5 Modes de Sauvegarde (configurables dans les Paramètres)

#### Mode 1 — Sauvegarde à l'extinction
- Lors de l'extinction de l'ordinateur, le logiciel **intercèpte l'événement d'arrêt**
- Une fenêtre de progression s'affiche : "Sauvegarde en cours avant extinction..."
- Le logiciel scanne les disques sources, compare, copie les fichiers modifiés/nouveaux
- Une fois terminé, il affiche "Sauvegarde terminée" et **libère le processus d'extinction**
- Si le disque cible est absent : fenêtre d'alerte avec 3 choix :
  - **Annuler l'extinction** (pour brancher le disque)
  - **Éteindre sans sauvegarde**
  - **Attendre X minutes** (pour brancher le disque)

#### Mode 2 — Sauvegarde planifiée
- Déclenchement à une **heure fixe** configurable (ex. : tous les jours à 22h00)
- S'exécute en arrière-plan, sans interrompre l'utilisation
- Notification systray à la fin : "Sauvegarde terminée — X fichiers mis à jour"
- Si le disque cible est absent à l'heure planifiée : notification d'alerte

> Les deux modes peuvent être **activés simultanément** (sauvegarde planifiée + sauvegarde à l'extinction)

### 5.6 Interface Utilisateur

#### Tableau de Bord (écran principal)
- Statut global : "Tout est à jour" / "Sauvegarde en cours" / "Action requise"
- Dernière sauvegarde : date, heure, nombre de fichiers copiés
- Espace utilisé sur le disque cible vs espace disponible (barre visuelle)
- Bouton **"Lancer une sauvegarde maintenant"**

#### Configuration des Disques
- Vue graphique des disques sources sélectionnés et du disque cible
- Ajout / suppression de disques sources en un clic
- Changement du disque cible

#### Paramètres
- Démarrage automatique au boot : ON/OFF
- Mode de sauvegarde : Extinction | Planifiée | Les deux
- Heure de sauvegarde planifiée
- Filtres d'exclusion (extensions, dossiers, taille max de fichier)
- **Destination de restauration par défaut** : Emplacement d'origine | Dossier fixe | Demander à chaque fois
- Langue (FR / EN — prévu pour internationalisation)
- Thème : Clair / Sombre

#### Historique
- Journal des sauvegardes (date, durée, fichiers copiés, erreurs)
- Export CSV

#### Révision des fichiers supprimés
- Liste des fichiers orphelins sur la cible
- Actions par fichier et actions globales

### 5.7 Restauration des Données

La restauration est accessible de **deux façons complémentaires** : depuis le menu contextuel de l'OS (clic droit) et depuis l'interface principale du logiciel.

#### Entrée de menu contextuel (clic droit dans l'explorateur de fichiers)

L'installateur enregistre une entrée "Restaurer depuis le dernier back-up" dans le menu contextuel natif de l'OS, disponible sur :
- **Un fichier unique**
- **Plusieurs fichiers sélectionnés simultanément** (multi-sélection)
- **Un dossier complet** (restauration récursive de tout le contenu)

| OS | Mécanisme |
|---|---|
| **Windows** | Entrée registre `HKEY_CLASSES_ROOT\*\shell\` (fichiers, multi-sélection) + `HKEY_CLASSES_ROOT\Directory\shell\` (dossiers) — ajoutée à l'installation, supprimée à la désinstallation |
| **macOS** | Quick Action (service Automator) installé dans `~/Library/Services/` — supporte la multi-sélection nativement |
| **Linux** | Scripts pour les gestionnaires de fichiers courants : Nautilus, Dolphin, Thunar |

**Workflow de restauration — étape par étape :**

```
1. Le logiciel reçoit le(s) chemin(s) du/des fichier(s) ou dossier(s) sélectionné(s)

2. Il recherche chaque élément dans le disque de sauvegarde
   → Si un élément est introuvable dans la sauvegarde :
       Fenêtre d'erreur : "Ce fichier n'a jamais été sauvegardé."
       Les autres éléments de la sélection continuent normalement.

3. Pour les éléments trouvés → Fenêtre de confirmation unique affichant :
   ┌─────────────────────────────────────────────────┐
   │  Restaurer depuis le back-up ?                  │
   │                                                 │
   │  Fichier(s) sélectionné(s) : 3                  │
   │  ├── rapport_2026.pdf  (sauvegardé le 13/04)    │
   │  ├── contrats/         (dossier, 42 fichiers)   │
   │  └── logo_final.png    (sauvegardé le 10/04)    │
   │                                                 │
   │  Destination : [emplacement d'origine    ▼]     │
   │                                                 │
   │  ⚠ Le(s) fichier(s) actuel(s) seront envoyés   │
   │    à la Corbeille avant restauration.           │
   │    Vous pourrez les récupérer si besoin.        │
   │                                                 │
   │     [Annuler]        [Restaurer]                │
   └─────────────────────────────────────────────────┘

4. L'utilisateur confirme → pour chaque élément :
   a. Le fichier/dossier actuel (s'il existe) est envoyé à la Corbeille
      (undo possible depuis la Corbeille de l'OS)
   b. La version sauvegardée est copiée vers la destination

5. Notification de succès : "3 éléments restaurés avec succès."
   (ou résumé partiel si certains ont échoué)
```

> **Sécurité undo** : l'envoi à la Corbeille avant restauration garantit que l'utilisateur peut toujours annuler l'opération en récupérant les fichiers depuis la Corbeille de son OS.

#### Restauration depuis l'interface principale (onglet "Restaurer")

- Arborescence navigable du disque de sauvegarde
- Recherche par nom de fichier
- Sélection d'un fichier, de plusieurs fichiers ou d'un dossier complet
- Le même workflow de confirmation s'applique (Corbeille → Restauration)
- Barre de progression pour les restaurations volumineuses
- Rapport de restauration (éléments restaurés, éléments ignorés, erreurs)

#### Destination de restauration (configurable dans les Paramètres)

Le comportement par défaut de la destination est personnalisable dans les Paramètres :

| Option | Description |
|---|---|
| **Emplacement d'origine** (défaut) | Restaure exactement où était le fichier |
| **Dossier fixe** | Toujours restaurer dans un dossier choisi par l'utilisateur |
| **Demander à chaque fois** | La fenêtre de confirmation affiche un sélecteur de dossier |

La destination peut aussi être modifiée ponctuellement dans la fenêtre de confirmation, quelle que soit l'option par défaut.

#### Cas limites gérés

| Situation | Comportement |
|---|---|
| Fichier absent de la sauvegarde | Message d'erreur explicite, pas d'action |
| Dossier sélectionné | Restauration récursive de tout le contenu |
| Multi-sélection avec éléments mixtes (trouvés/non trouvés) | Restaure les éléments trouvés, liste les éléments manquants |
| Disque cible absent | Fenêtre d'alerte "Disque de sauvegarde introuvable" |
| Espace insuffisant à la destination | Alerte avant de démarrer la restauration |
| Corbeille pleine ou indisponible | Alerte + demande confirmation pour supprimer directement |

### 5.8 Notifications & Alertes

| Événement | Notification |
|---|---|
| Sauvegarde terminée | Toast systray : "X fichiers mis à jour" |
| Disque cible absent | Fenêtre modale bloquante avec options |
| Fichiers supprimés détectés | Bannière au démarrage "X fichiers à réviser" |
| Erreur de copie | Toast d'erreur avec détail du fichier concerné |
| Espace disque < 10 % | Alerte d'avertissement |
| Restauration réussie | Toast : "Fichier restauré avec succès" |
| Fichier absent de la sauvegarde | Fenêtre d'erreur explicite |

---

## 6. Stack Technique

| Composant | Choix | Justification |
|---|---|---|
| Langage principal | **Python 3.12** | Stable, lisible, cross-plateforme, écosystème riche |
| Interface graphique | **PySide6 (Qt 6)** | Qt = 30 ans de maturité, natif sur tous les OS, systray intégré, interception extinction native |
| Hachage fichiers | **xxhash (lib Python)** | Implémentation C, le plus rapide des algorithmes non-cryptographiques, fiable |
| Systray & notifications | PySide6 `QSystemTrayIcon` | Natif Qt |
| Interception extinction | Qt `QSessionManager` | Intercepte `WM_QUERYENDSESSION` (Windows), `NSApplicationDelegate` (macOS), systemd inhibitor (Linux) |
| Planificateur | **APScheduler** | Léger, cross-plateforme, pas de dépendance externe |
| Packaging / installateur | **PyInstaller** + scripts d'install natifs | Génère `.exe` (Windows), `.app` (macOS), `.deb`/`.AppImage` (Linux) |
| Config utilisateur | Fichier **JSON** local | Pas de base de données, lisible, versionnable |
| Logs | Fichiers **JSON Lines** horodatés | Lisibles et exploitables |

### Librairies Python requises
```
PySide6          # GUI Qt6
xxhash           # Hachage fichiers (xxh3)
apscheduler      # Planificateur de tâches
psutil           # Infos disques (espace, montage)
pyinstaller      # Packaging (dev uniquement)
```

---

## 7. Architecture

```
┌─────────────────────────────────────────────────┐
│                    GUI (PySide6)                 │
│  Dashboard | Config | Paramètres | Historique    │
│  Révision fichiers supprimés | Restaurer | Systray│
└───────────────────┬─────────────────────────────┘
                    │ signaux Qt
┌───────────────────▼─────────────────────────────┐
│                 Core Engine                      │
│  ┌──────────────┐  ┌────────────────────────┐   │
│  │  Scanner     │  │  Comparator (xxHash)   │   │
│  │  (disques)   │  │  (xxh3 par fichier)    │   │
│  └──────┬───────┘  └──────────┬─────────────┘   │
│         │                     │                  │
│  ┌──────▼─────────────────────▼─────────────┐   │
│  │         Copy Engine                       │   │
│  │  (copie incrémentale + rapport)           │   │
│  └──────────────────┬────────────────────────┘   │
│                     │                            │
│  ┌──────────────────▼────────────────────────┐  │
│  │     Orphan Manager                        │  │
│  │  (suivi fichiers supprimés de la source)  │  │
│  └───────────────────────────────────────────┘  │
│                                                  │
│  ┌───────────────────────────────────────────┐  │
│  │     Scheduler (APScheduler)               │  │
│  └───────────────────────────────────────────┘  │
│                                                  │
│  ┌───────────────────────────────────────────┐  │
│  │     Shutdown Handler (QSessionManager)    │  │
│  └───────────────────────────────────────────┘  │
│                                                  │
│  ┌───────────────────────────────────────────┐  │
│  │     Restore Engine                        │  │
│  │  (recherche dans cible + copie inverse)   │  │
│  │  ← déclenché par GUI ou menu contextuel   │  │
│  └───────────────────────────────────────────┘  │
│                                                  │
│  ┌───────────────────────────────────────────┐  │
│  │     OS Context Menu Handler               │  │
│  │  (Windows registry / macOS Quick Action   │  │
│  │   / Linux file manager scripts)           │  │
│  └───────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────┐
│              Storage Layer                       │
│  Disques locaux | Disques externes               │
│  (lecture source + écriture cible)               │
└──────────────────────────────────────────────────┘
```

---

## 8. Structure des Fichiers de Config

```json
{
  "version": "1.0",
  "autostart": true,
  "theme": "dark",
  "language": "fr",
  "backup": {
    "mode": "both",
    "scheduled_time": "22:00",
    "target_disk": "E:\\",
    "source_disks": ["C:\\", "D:\\"]
  },
  "filters": {
    "excluded_extensions": [".tmp", ".log", ".DS_Store"],
    "excluded_folders": ["node_modules", "__pycache__", "$RECYCLE.BIN"],
    "max_file_size_gb": 0
  }
}
```

---

## 9. Hors Scope (v1.0)

- Chiffrement des données
- Compression des archives
- Stockage cloud (S3, Google Drive, Backblaze…)
- Sauvegarde de bases de données (dump SQL)
- Historique de versions multiples par fichier (une seule version sauvegardée en v1.0)
- Dashboard web headless
- Alertes email / webhook

---

## 10. Risques

| Risque | Probabilité | Impact | Mitigation |
|---|---|---|---|
| Permissions OS restrictives (macOS SIP) | Haute | Moyen | Demander les permissions au premier lancement |
| Disque source démonté en cours de scan | Moyenne | Élevé | Vérification de montage avant et pendant l'opération |
| Espace disque cible saturé | Moyenne | Élevé | Vérification avant copie + alerte bloquante |
| Extinction forcée (power cut) pendant sauvegarde | Faible | Moyen | Copie atomique (temp file + rename) pour éviter fichiers corrompus |
| Performance sur très gros volume (> 1 To de delta) | Faible | Moyen | Copie en thread séparé, barre de progression, possibilité d'annuler |
| Écrasement accidentel lors d'une restauration | Faible | Élevé | Fichier actuel envoyé à la Corbeille avant restauration — undo toujours possible |
| Menu contextuel non enregistré après mise à jour OS | Faible | Moyen | Re-enregistrement des entrées registre/service à chaque mise à jour du logiciel |

---

## 11. Jalons

| Jalon | Livrable |
|---|---|
| M0 — Cadrage ✅ | PRD validé, stack technique arrêtée |
| M1 — Core Engine | Scanner + Comparator xxHash + Copy Engine (CLI de test) |
| M2 — Shutdown Handler | Interception extinction + progression + libération |
| M3 — Orphan Manager | Détection et révision des fichiers supprimés |
| M4 — Restore Engine | Restauration fichier/dossier + menu contextuel OS |
| M5 — GUI v1 | Interface PySide6 : Dashboard, Config disques, Restaurer, Paramètres |
| M6 — Planificateur | Mode sauvegarde planifiée + notifications systray |
| M7 — Packaging | Installateurs natifs Windows / macOS / Linux |
| M8 — Beta | Tests utilisateurs, correctifs, polish UI |
| M9 — v1.0 | Release publique sur GitHub (MIT) |
