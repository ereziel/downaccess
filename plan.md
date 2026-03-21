# Plan de développement — DownAccess

## Architecture des fichiers

```
dl/
├── main.py                      # Point d'entrée, initialise wx.App
├── requirements.txt             # Dépendances pip
├── downaccess.spec              # PyInstaller one-dir spec
├── version_info.txt             # Métadonnées Windows pour l'exe
├── context.md                   # Contexte technique du projet
├── plan.md                      # Ce fichier — features et avancement
├── CLAUDE.md                    # Instructions pour Claude Code
│
├── app/
│   ├── version.py               # __version__ centralisé (ex: "0.1.0")
│   │
│   ├── core/                    # Logique métier (aucun import wx ici)
│   │   ├── downloader.py        # Wrapper yt-dlp, extrait infos + télécharge (mode verbose)
│   │   ├── queue_manager.py     # Gestion de la file, priorités, concurrence
│   │   ├── postprocessor.py     # Appels ffmpeg (conversion, extraction audio)
│   │   ├── settings.py          # Lecture/écriture settings.json (incl. user_email)
│   │   ├── updater.py           # Mise à jour yt-dlp (bootstrap AppData)
│   │   ├── app_updater.py       # Auto-update DownAccess (GitHub Releases)
│   │   └── error_reporter.py    # Rapport d'erreur + contact (POST HTTPS → backend PHP)
│   │
│   └── ui/                      # Composants wxPython
│       ├── main_window.py       # wx.Frame principal, layout, menu bar
│       ├── download_list.py     # wx.ListCtrl (queue avec statut/progression)
│       ├── add_url_dialog.py    # Dialogue ajout d'URL(s) + options par téléchargement
│       ├── settings_dialog.py   # Dialogue préférences globales
│       ├── format_dialog.py     # Sélecteur de format/qualité
│       ├── playlist_dialog.py   # Sélection vidéos dans une playlist
│       ├── search_dialog.py     # Recherche YouTube/SoundCloud/Bilibili
│       ├── uge_dialog.py        # User Guided Extraction (WebView2 intégré)
│       ├── update_dialog.py     # Dialogue mise à jour avec release notes
│       ├── error_dialog.py      # Dialogue erreur téléchargement + bouton rapport
│       ├── report_dialog.py     # Rapport d'erreur avec diagnostic yt-dlp verbose
│       └── contact_dialog.py    # Formulaire de contact / suggestion
│
└── installer/
    └── downaccess.iss           # Script Inno Setup (install utilisateur, sans dialogue UAC)
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

- `[x]` Support des playlists : détecter, proposer téléchargement sélectif (PlaylistDialog)
- `[ ]` Pause / reprise d'un téléchargement
- `[ ]` Annulation d'un téléchargement
- `[ ]` Réordonner la file (monter/descendre un item)
- `[x]` Réessayer un téléchargement échoué (F2)
- `[x]` Ouvrir le dossier de destination quand tout est terminé (réglage Préférences)
- `[ ]` Sous-titres : téléchargement automatique selon préférences
- `[ ]` Sous-titres : conversion en .srt via ffmpeg si nécessaire
- `[ ]` Organisation automatique : sous-dossier par site ou par playlist
- `[x]` Ctrl+V dans la fenêtre principale → colle et enqueue directement sans dialogue
- `[x]` Surveillance du presse-papiers (timer 1,5 s, activable via menu ou Ctrl+Shift+V, persisté dans settings)
- `[x]` Recherche intégrée : YouTube, SoundCloud, Bilibili (Ctrl+F)
- `[x]` User Guided Extraction : WebView2 intégré avec profil persistent + F6 pour capturer l'URL

### Phase 6 — Accessibilité NVDA avancée

- `[x]` Vérification complète du parcours tabulation sur tous les dialogues
- `[x]` Annonces vocales sur les événements clés via `speech.speak()` (accessible_output2)
- `[x]` Raccourcis clavier documentés via menu Aide
- `[x]` Focus initial des dialogues sur le contenu (pas le bouton) pour permettre lecture NVDA
- `[ ]` Test de lecture NVDA sur chaque état de la ListCtrl (en attente, en cours, terminé, erreur)
- `[ ]` Contraste des couleurs conforme WCAG AA

### Phase 7 — Distribution

- `[x]` Packaging avec PyInstaller (one-dir, ~143 MB dossier)
- `[x]` ffmpeg inclus via imageio-ffmpeg dans le bundle
- `[x]` `app/core/updater.py` : mise à jour yt-dlp dans `%APPDATA%\DownAccess\yt-dlp\`
- `[x]` Inno Setup : installeur silencieux (install utilisateur, sans dialogue UAC), toujours `DownAccess-Setup.exe`
- `[x]` GitHub Releases : release `v0.1.1` publiée avec l'installeur (schéma numérique, pas de suffixe beta)
- `[x]` Auto-updater DownAccess : vérification au démarrage + `UpdateDialog` (release notes + boutons)
- `[x]` Rapport d'erreur : re-run verbose yt-dlp + envoi JSON au backend PHP via HTTPS + Bearer token
- `[x]` Formulaire de contact/suggestion : type, email obligatoire, message — menu Aide
- `[x]` Email utilisateur mémorisé dans settings.json et pré-rempli dans les deux formulaires
- `[ ]` Icône personnalisée (assets/icon.ico) pour l'exe et l'installeur
- `[ ]` Code signing (certificat) pour éviter les alertes SmartScreen

### À venir (backlog)

- `[ ]` Historique des téléchargements (base SQLite ou JSON)
- `[ ]` Cookies depuis le navigateur (Edge/Chrome) pour contenu premium
- `[ ]` Téléchargement par lot : coller plusieurs URLs (une par ligne) — déjà partiel via add_url_dialog
- `[ ]` Sous-titres automatiques
- `[ ]` Organisation par site/playlist

---

## Raccourcis clavier

| Action                              | Raccourci          |
|-------------------------------------|--------------------|
| Ajouter URL(s)                      | Ctrl+N             |
| Recherche intégrée                  | Ctrl+F             |
| Coller URL depuis presse-papiers    | Ctrl+V             |
| Surveillance presse-papiers on/off  | Ctrl+Shift+V       |
| Démarrer la file                    | F5                 |
| Réessayer sélectionné               | F2                 |
| Supprimer sélectionné               | Suppr              |
| Ouvrir dossier de destination       | Ctrl+O             |
| Préférences                         | Ctrl+P             |
| User Guided Extraction              | Menu Outils        |
| Retour app depuis WebView           | F6                 |
| Quitter                             | Alt+F4             |

---

## Décisions techniques prises

- **wx.ListCtrl** (Report style) plutôt que wx.dataview ou wx.grid → meilleur support NVDA/MSAA natif.
- **yt-dlp via import Python** (pas subprocess) → accès aux hooks de progression natifs.
- **ffmpeg via subprocess** → plus simple, ffmpeg reste un binaire externe.
- **settings.json** dans `%APPDATA%\DownAccess\` → standard Windows pour les préférences utilisateur.
- **Threading standard Python** avec `wx.CallAfter` pour les callbacks UI → évite les deadlocks wxPython.
- **WebView2 profil persistent** dans `%APPDATA%\DownAccess\WebView2Profile\` → bypass Cloudflare naturel.
- **Installeur toujours nommé `DownAccess-Setup.exe`** (sans version) → URL fixe pour l'auto-updater.
- **Focus initial sur le contenu** dans les dialogues informatifs → utilisateur lit avant d'agir (NVDA).
- **PyInstaller one-dir** (pas one-file) → démarrage plus rapide, pas d'extraction au lancement.
