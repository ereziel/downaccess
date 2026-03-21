# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Projet

**DownAccess** — application Windows de téléchargement vidéo/audio, équivalente à Downie (macOS). Le nom reflète Download + Access + Accessibility. Voir `context.md` pour le contexte technique complet et `plan.md` pour les fonctionnalités et l'état d'avancement.

## Commandes de développement

```bash
# Créer et activer le venv
python -m venv venv
source venv/Scripts/activate   # Git Bash / bash on Windows

# Installer les dépendances
pip install -r requirements.txt

# Lancer l'application
python main.py

# Mettre à jour yt-dlp (à faire régulièrement)
pip install -U yt-dlp
```

## Architecture

```
app/core/      Logique métier pure — aucun import wx autorisé ici
app/ui/        Composants wxPython uniquement
```

**Flux principal :**
1. `main.py` → crée `wx.App` + `MainWindow`
2. L'utilisateur ajoute une URL → `AddUrlDialog` → `QueueManager.add()`
3. `QueueManager` démarre un thread → `Downloader.download()` (yt-dlp)
4. Les callbacks de progression appellent `wx.CallAfter(...)` pour mettre à jour `DownloadList`
5. Après téléchargement → `PostProcessor` (ffmpeg) si configuré

**Communication inter-threads :** toujours via `wx.CallAfter()` ou `wx.PostEvent()`. Ne jamais appeler de méthode wx directement depuis un thread non-UI.

## Règles d'accessibilité NVDA (non négociables)

- Utiliser uniquement des contrôles wx natifs (pas de custom drawing)
- Chaque `wx.TextCtrl` doit avoir un `wx.StaticText` label associé juste avant dans le layout
- Chaque bouton doit avoir un label textuel descriptif (jamais icône seule)
- Les mises à jour de progression doivent aussi mettre à jour la `wx.StatusBar`
- Tester le parcours Tab sur chaque dialogue — l'ordre doit être logique
- Les erreurs s'affichent via `wx.MessageDialog` (lu automatiquement par NVDA)

## Décisions d'architecture

- `wx.ListCtrl` (Report style) pour la queue — meilleur support MSAA/UIA natif vs wx.dataview
- yt-dlp utilisé via import Python (pas subprocess) → accès aux hooks `progress_hooks` natifs
- ffmpeg utilisé via subprocess → binaire externe, chemin configurable
- Préférences stockées dans `%APPDATA%\DownAccess\settings.json`
