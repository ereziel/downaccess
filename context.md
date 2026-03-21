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
| ffmpeg bundle   | imageio-ffmpeg         | Binaire ffmpeg inclus dans le build PyInstaller  |
| Persistance     | JSON (settings.json)   | Sauvegarde des préférences utilisateur           |
| Nom produit     | DownAccess             | Download + Access + Accessibility                |
| Threads         | Python threading/queue | Téléchargements en arrière-plan sans bloquer l'UI|
| Distribution    | PyInstaller + Inno Setup | Build one-dir + installeur silencieux           |
| Auto-update     | GitHub Releases API    | Vérification + téléchargement du nouvel installeur|
| Rapport d'erreur | Backend PHP + PHPMailer | Re-run verbose yt-dlp → POST JSON → email        |

## Accessibilité NVDA — règles impératives

- **Aucun contrôle custom-drawn** : utiliser uniquement des wx controls natifs (ListCtrl, Button, TextCtrl, etc.) qui exposent MSAA/UIA automatiquement.
- **Tous les boutons ont un label textuel** clair. Pas de boutons icône seul.
- **Toutes les TextCtrl ont un label wx.StaticText** associé via `SetLabel` ou `MakeModal`.
- **Ordre de tabulation logique** défini explicitement via `MoveAfterInTabOrder`.
- **Raccourcis clavier** pour toutes les actions principales (Ctrl+V = coller URL, Suppr = supprimer de la queue, Espace = pause/reprendre, F5 = démarrer).
- **Annonces de progression** : mettre à jour la StatusBar ET le label accessible de l'item de liste pour que NVDA puisse lire l'état.
- **Dialogues modaux** : focus initial sur le **contenu** (TextCtrl, liste) et non sur le bouton principal, pour permettre à l'utilisateur de lire avant d'agir.
- **Messages d'erreur** : utiliser `wx.MessageDialog` (NVDA le lit automatiquement).
- Ne jamais utiliser de couleur seule pour communiquer un état — toujours doubler avec du texte.
- `speech.speak()` via `accessible_output2` pour les annonces hors-dialogue (progression, mises à jour disponibles, etc.).

## Environnement de développement

- OS : Windows 11 Pro
- Shell : bash (Git Bash / WSL)
- Python : via venv (`venv/`)
- Dépendances Python : `requirements.txt`
- ffmpeg : inclus via `imageio-ffmpeg` dans le build, configurable manuellement dans les préférences
- Répertoire de travail : `C:\Users\mathi\dev\dl`
- Inno Setup 6 : installé dans `C:\Users\mathi\AppData\Local\Programs\Inno Setup 6\`

## Distribution

- **Build PyInstaller** : `pyinstaller downaccess.spec --noconfirm` → `dist/DownAccess/`
- **Build installeur** : `powershell.exe -Command "& 'C:\Users\mathi\AppData\Local\Programs\Inno Setup 6\ISCC.exe' 'installer\downaccess.iss'"` → `installer_output/DownAccess-Setup.exe`
- **Release GitHub** : `gh release upload vX.Y.Z installer_output/DownAccess-Setup.exe --clobber`
- L'installeur est toujours nommé `DownAccess-Setup.exe` (sans numéro de version) pour que l'auto-updater puisse le télécharger depuis l'URL fixe.

## Rapport d'erreur et contact

- `app/core/error_reporter.py` : `build_report()` + `send_report()` + `send_contact()` — POST JSON via HTTPS avec `Authorization: Bearer <secret>`
- En cas d'échec de téléchargement, `ErrorDialog` propose un bouton "Envoyer un rapport d'erreur"
- `ReportDialog` : champ email (pré-rempli depuis settings) + commentaire ; lance un re-run yt-dlp en mode verbose dans un thread, capture les logs, envoie tout au backend PHP
- `ContactDialog` : type de message + email + message libre — accessible depuis menu Aide → "Contacter le support"
- L'email saisi est sauvegardé dans `settings.json` (`user_email`) et pré-rempli à la prochaine ouverture
- Backend PHP sur `mathieumartin.ovh` : deux endpoints `/api/downaccess-report` et `/api/downaccess-contact`, rate limiting par IP, envoi email via PHPMailer + SMTP OVH
- Les dialogues restent ouverts pendant l'envoi asynchrone et affichent le résultat avant de permettre la fermeture

## Auto-updater

- `app/core/app_updater.py` vérifie l'API GitHub Releases au démarrage (thread daemon)
- Si une version supérieure est détectée, `UpdateDialog` s'affiche avec les release notes et deux boutons
- L'utilisateur choisit "Mettre à jour maintenant" ou "Plus tard"
- Téléchargement dans `%TEMP%/DownAccess-Setup.exe.tmp`, renommé uniquement si complet (> 64 KB)
- L'installeur est lancé via `subprocess.Popen`, l'app se ferme proprement si le processus a démarré

## User Guided Extraction (UGE)

- `app/ui/uge_dialog.py` : navigateur WebView2 (Edge) intégré avec profil persistent (`%APPDATA%\DownAccess\WebView2Profile\`)
- Profil persistent → cookies accumulés entre sessions → Cloudflare bypass naturel
- F6 dans le WebView → JS keydown listener → `window.location.assign('downaccess://f6')` → intercepté dans `_on_navigating` → retourne à l'app
- Referer et cookies extraits du WebView et passés à yt-dlp pour les médias protégés
- Résolution des redirections HTTP + parsing JSON pour trouver les vraies URLs de médias

## Recherche intégrée

- `app/ui/search_dialog.py` : deux dialogues — `SearchDialog` (requête + site + nombre de résultats) et `SearchResultsDialog` (ListCtrl avec cases à cocher + choix de format)
- Sites supportés : YouTube (`ytsearch`), SoundCloud (`scsearch`), Bilibili (`bilisearch`)
- Accessible via Ctrl+F depuis la fenêtre principale

## Conventions de code

- PEP 8, snake_case pour variables/fonctions, PascalCase pour classes
- `app/core/` : logique métier pure — **aucun import wx autorisé**
- `app/ui/` : composants wxPython uniquement
- Les appels yt-dlp se font dans des threads séparés — jamais dans le thread principal wx
- Communiquer entre threads via `wx.CallAfter` pour les mises à jour UI
- Les messages d'erreur yt-dlp/ffmpeg sont capturés et affichés proprement à l'utilisateur
