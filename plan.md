# Plan de développement — DownAccess

## Architecture des fichiers

```
dl/
├── main.py                      # Point d'entrée, initialise wx.App
├── requirements.txt             # Dépendances pip
├── context.md                   # Contexte technique du projet
├── plan.md                      # Ce fichier — features et avancement
├── CLAUDE.md                    # Instructions pour Claude Code
│
├── app/
│   ├── __init__.py
│   │
│   ├── core/                    # Logique métier (aucun import wx ici)
│   │   ├── __init__.py
│   │   ├── downloader.py        # Wrapper yt-dlp, extrait infos + télécharge
│   │   ├── queue_manager.py     # Gestion de la file, priorités, concurrence
│   │   ├── postprocessor.py     # Appels ffmpeg (conversion, extraction audio)
│   │   └── settings.py          # Lecture/écriture settings.json
│   │
│   └── ui/                      # Composants wxPython
│       ├── __init__.py
│       ├── main_window.py       # wx.Frame principal, layout, menu bar
│       ├── download_list.py     # wx.ListCtrl (queue avec statut/progression)
│       ├── add_url_dialog.py    # Dialogue ajout d'URL(s) + options par téléchargement
│       ├── settings_dialog.py   # Dialogue préférences globales
│       └── format_dialog.py     # Sélecteur de format/qualité
```

---

## Features et état d'avancement

### Légende
- `[ ]` Non commencé
- `[~]` En cours
- `[x]` Terminé

---

### Phase 1 — Squelette et infrastructure

- `[x]` Initialisation du projet (venv, requirements.txt, structure de dossiers)
- `[x]` `main.py` : lancement wx.App, création MainWindow
- `[x]` `app/core/settings.py` : lecture/écriture `settings.json` avec valeurs par défaut
- `[x]` `app/ui/main_window.py` : fenêtre principale avec menu bar, status bar, layout de base
- `[x]` `app/ui/download_list.py` : wx.ListCtrl Report avec colonnes (Titre, Site, Statut, Progression, Taille)

### Phase 2 — Ajout d'URL et téléchargement de base

- `[x]` `app/ui/add_url_dialog.py` : champ URL(s) multi-lignes, bouton OK/Annuler, accessible NVDA
- `[x]` `app/core/downloader.py` : extraction d'infos via `yt_dlp.YoutubeDL` (titre, thumbnail, formats disponibles)
- `[x]` `app/core/downloader.py` : téléchargement dans un thread séparé avec callbacks de progression
- `[x]` `app/core/queue_manager.py` : file FIFO, limite de téléchargements simultanés configurable
- `[x]` Mise à jour de la ListCtrl en temps réel via `wx.CallAfter`
- `[x]` Gestion des erreurs yt-dlp (site non supporté, URL invalide, accès refusé)

### Phase 3 — Sélection de format et post-traitement

- `[x]` `app/ui/format_dialog.py` : liste des formats disponibles (résolution, codec, taille estimée)
- `[x]` Option "meilleure qualité automatique" (défaut)
- `[x]` Option "préférer MP4" (remux ou conversion via ffmpeg)
- `[x]` Extraction audio → MP3 (via yt-dlp FFmpegExtractAudio)
- `[x]` Extraction audio → M4A
- `[x]` Conversion vidéo → MP4 H.264
- `[x]` Option "aucun post-traitement" (fichier brut)
- `[x]` Mode manuel : fetch info → FormatDialog → format_id spécifique

### Phase 4 — Préférences et configuration

- `[x]` `app/ui/settings_dialog.py` : dialogue avec onglets
  - `[x]` Onglet Général : dossier de destination, nombre de téléchargements simultanés, action après téléchargement
  - `[x]` Onglet Formats : post-traitement par défaut (aucun / MP4 / audio MP3 / audio M4A)
  - `[x]` Onglet Sous-titres : télécharger automatiquement, langue(s) préférée(s), format (srt / vtt / original)
  - `[x]` Onglet Réseau : proxy HTTPS, proxy SOCKS4/5, User-Agent personnalisé
  - `[x]` Onglet Avancé : chemin ffmpeg, options yt-dlp supplémentaires (raw)

### Phase 5 — Fonctionnalités avancées

- `[ ]` Support des playlists : détecter, proposer téléchargement sélectif ou complet
- `[ ]` Téléchargement par lot : coller plusieurs URLs (une par ligne)
- `[ ]` Pause / reprise d'un téléchargement
- `[ ]` Annulation d'un téléchargement
- `[ ]` Réordonner la file (monter/descendre un item)
- `[x]` Réessayer un téléchargement échoué (F2)
- `[x]` Ouvrir le dossier de destination quand tout est terminé (réglage Préférences)
- `[x]` Support des playlists : détecter, proposer téléchargement sélectif (PlaylistDialog)
- `[ ]` Sous-titres : téléchargement automatique selon préférences
- `[ ]` Sous-titres : conversion en .srt via ffmpeg si nécessaire
- `[ ]` Organisation automatique : sous-dossier par site ou par playlist
- `[x]` Ctrl+V dans la fenêtre principale → colle et enqueue directement sans dialogue
- `[x]` Surveillance du presse-papiers (timer 1,5 s, activable via menu ou Ctrl+Shift+V, persisté dans settings)

### Phase 6 — Accessibilité NVDA avancée

- `[ ]` Vérification complète du parcours tabulation sur tous les dialogues
- `[ ]` Test de lecture NVDA sur chaque état de la ListCtrl (en attente, en cours, terminé, erreur)
- `[ ]` Annonces vocales sur les événements clés (téléchargement démarré, terminé, erreur)
- `[ ]` Raccourcis clavier documentés et accessibles via menu Aide
- `[ ]` Contraste des couleurs conforme WCAG AA (même si NVDA est la cible principale)

### Phase 7 — Distribution

- `[ ]` Packaging avec PyInstaller (exécutable standalone Windows)
- `[ ]` Inclusion de ffmpeg dans le bundle ou détection automatique
- `[x]` `app/core/updater.py` : installation de yt-dlp dans `%APPDATA%\DownAccess\yt-dlp\` et mise à jour via pip
- `[x]` Injection AppData dans `sys.path` au démarrage (`updater.bootstrap()` dans `main.py`)
- `[x]` Menu Aide → "Mettre à jour yt-dlp" avec feedback barre de statut + `wx.MessageBox`

---

## Raccourcis clavier cibles

| Action                        | Raccourci       |
|-------------------------------|-----------------|
| Ajouter URL(s)                | Ctrl+N          |
| Coller URL depuis presse-papiers | Ctrl+V (dans dialogue) |
| Démarrer la file              | F5              |
| Pause / reprendre sélectionné | Espace          |
| Annuler sélectionné           | Suppr           |
| Réessayer sélectionné         | F2              |
| Ouvrir dossier de destination | Ctrl+O          |
| Préférences                   | Ctrl+,          |
| Quitter                       | Alt+F4          |

---

## Décisions techniques prises

- **wx.ListCtrl** (Report style) plutôt que wx.dataview ou wx.grid → meilleur support NVDA/MSAA natif.
- **yt-dlp via import Python** (pas subprocess) → accès aux hooks de progression natifs.
- **ffmpeg via subprocess** → plus simple, ffmpeg reste un binaire externe.
- **settings.json** dans `%APPDATA%\DownAccess\` → standard Windows pour les préférences utilisateur.
- **Threading standard Python** avec `wx.CallAfter` pour les callbacks UI → évite les deadlocks wxPython.
