# DownAccess

Téléchargeur vidéo et audio Windows, **100 % accessible NVDA**.
Équivalent de [Downie](https://software.charliemonroe.net/downie/) pour macOS.

---

## Fonctionnalités

- **Téléchargement** de vidéos et audios depuis des centaines de sites (YouTube, SoundCloud, Dailymotion, Twitch, etc.) via [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- **Extraction guidée (UGE)** — navigateur intégré (WebView2) pour détecter automatiquement les médias sur n'importe quelle page
- **Recherche intégrée** — YouTube, SoundCloud sans quitter l'app
- **Sélection de format** — Auto, MP4, MP3, M4A, ou choix manuel parmi tous les formats disponibles
- **Playlists** — détection automatique, sélection individuelle des épisodes
- **Sous-titres** — téléchargement automatique dans la langue de votre choix
- **File de téléchargement** — pause, reprise, annulation, réordonnancement
- **Surveillance du presse-papiers** — ajoute automatiquement les URLs copiées
- **ffmpeg embarqué** — aucune installation manuelle requise
- **Mise à jour automatique de yt-dlp** au démarrage

## Accessibilité NVDA

DownAccess est conçu pour être 100 % utilisable avec NVDA :

- Contrôles wxPython natifs (MSAA / UIA)
- Annonces vocales via [accessible_output2](https://github.com/accessibleapps/accessible_output2) (pas de notifications Windows)
- Jalons de progression annoncés (25 / 50 / 75 %)
- Ordre Tab logique sur tous les dialogues
- Cases à cocher natives dans les listes (ListCtrl + EnableCheckBoxes)
- Raccourcis clavier complets

## Raccourcis clavier

| Raccourci | Action |
|---|---|
| `Ctrl+N` | Ajouter URL(s) |
| `Ctrl+F` | Rechercher (YouTube, SoundCloud…) |
| `Ctrl+G` | Extraction guidée (navigateur intégré) |
| `Ctrl+V` | Coller URL depuis le presse-papiers |
| `Ctrl+Shift+V` | Activer/désactiver la surveillance du presse-papiers |
| `F5` | Démarrer la file |
| `Espace` | Pause / Reprendre |
| `Suppr` | Annuler / Supprimer |
| `F2` | Réessayer |
| `Alt+Haut` | Monter dans la file |
| `Alt+Bas` | Descendre dans la file |
| `Ctrl+O` | Ouvrir le dossier de destination |
| `Ctrl+P` | Préférences |
| `Alt+F4` | Quitter |

## Installation (développement)

**Prérequis :** [UV](https://docs.astral.sh/uv/) (gestionnaire de paquets Python). UV installe automatiquement la bonne version de Python (3.14, cf. `.python-version`).

```bash
git clone https://github.com/votre-compte/downaccess.git
cd downaccess

uv sync               # crée .venv + installe toutes les dépendances (lock reproductible)
uv run python main.py # lance l'application
```

## Dépendances

| Package | Rôle |
|---|---|
| [wxPython](https://wxpython.org/) | Interface graphique native Windows |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | Moteur de téléchargement |
| [imageio-ffmpeg](https://github.com/imageio/imageio-ffmpeg) | ffmpeg embarqué (conversion audio/vidéo) |
| [accessible_output2](https://github.com/accessibleapps/accessible_output2) | Synthèse vocale NVDA/JAWS |

## Architecture

```
app/
├── core/          # Logique métier pure (pas de wx ici)
│   ├── downloader.py      # Wrapper yt-dlp
│   ├── queue_manager.py   # File de téléchargement (threads)
│   ├── updater.py         # Mise à jour yt-dlp
│   ├── settings.py        # Préférences (AppData)
│   ├── speech.py          # Wrapper accessible_output2
│   └── ffmpeg_utils.py    # Résolution chemin ffmpeg
└── ui/            # Composants wxPython
    ├── main_window.py     # Fenêtre principale
    ├── add_url_dialog.py  # Ajout d'URL
    ├── search_dialog.py   # Recherche intégrée
    ├── uge_dialog.py      # Extraction guidée
    ├── format_dialog.py   # Sélection de format
    ├── playlist_dialog.py # Sélection d'épisodes
    ├── settings_dialog.py # Préférences (5 onglets)
    └── download_list.py   # Liste de téléchargements
```

## Licence

MIT
