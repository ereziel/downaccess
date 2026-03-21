# Contexte du projet — DownAccess (Windows Video Downloader)

## Vision

Application Windows équivalente à Downie (macOS), pour télécharger des vidéos et audios depuis des centaines de sites web. L'application doit être **100% accessible avec NVDA** (screen reader Windows).

## Stack technique

| Composant       | Outil                  | Rôle                                             |
|-----------------|------------------------|--------------------------------------------------|
| Langage         | Python 3.11+           | Langage principal                                |
| GUI             | wxPython (Phoenix)     | Interface graphique native Windows               |
| Téléchargement  | yt-dlp                 | Backend de téléchargement (1200+ sites)          |
| Post-traitement | ffmpeg / ffprobe       | Conversion, extraction audio, fusion flux        |
| Persistance     | JSON (settings.json)   | Sauvegarde des préférences utilisateur           |
| Nom produit     | DownAccess             | Download + Access + Accessibility                |
| Threads         | Python threading/queue | Téléchargements en arrière-plan sans bloquer l'UI|

## Accessibilité NVDA — règles impératives

- **Aucun contrôle custom-drawn** : utiliser uniquement des wx controls natifs (ListCtrl, Button, TextCtrl, etc.) qui exposent MSAA/UIA automatiquement.
- **Tous les boutons ont un label textuel** clair. Pas de boutons icône seul.
- **Toutes les TextCtrl ont un label wx.StaticText** associé via `SetLabel` ou `MakeModal`.
- **Ordre de tabulation logique** défini explicitement via `MoveAfterInTabOrder`.
- **Raccourcis clavier** pour toutes les actions principales (Ctrl+V = coller URL, Suppr = supprimer de la queue, Espace = pause/reprendre, F5 = démarrer).
- **Annonces de progression** : mettre à jour la StatusBar ET le label accessible de l'item de liste pour que NVDA puisse lire l'état.
- **Dialogues modaux** : focus doit aller sur le premier contrôle interactif à l'ouverture.
- **Messages d'erreur** : utiliser `wx.MessageDialog` (NVDA le lit automatiquement).
- Ne jamais utiliser de couleur seule pour communiquer un état — toujours doubler avec du texte.

## Environnement de développement

- OS : Windows 11 Pro
- Shell : bash (Git Bash / WSL)
- Python : via venv (`venv/`)
- Dépendances Python : `requirements.txt`
- ffmpeg : binaire externe, chemin configurable dans les préférences
- Répertoire de travail : `C:\Users\mathi\dev\dl`

## Conventions de code

- PEP 8, snake_case pour variables/fonctions, PascalCase pour classes
- Chaque module a une responsabilité unique (pas de logique métier dans les fichiers UI)
- Les appels yt-dlp se font dans des threads séparés — jamais dans le thread principal wx
- Communiquer entre threads via `wx.CallAfter` pour les mises à jour UI
- Les messages d'erreur yt-dlp/ffmpeg sont capturés et affichés proprement à l'utilisateur
