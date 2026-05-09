import subprocess

import wx

from app.core import settings as cfg
from app.core import speech
from app.core.ffmpeg_utils import get_ffmpeg_path

# Valeurs des choix de post-traitement (index → clé settings)
POST_CHOICES = ["none", "mp4", "mp3", "m4a"]
POST_LABELS  = ["Aucun (fichier brut)", "Vidéo MP4 (H.264)", "Audio MP3", "Audio M4A"]

SUBTITLE_FORMAT_CHOICES = ["srt", "vtt", "original"]
SUBTITLE_FORMAT_LABELS  = ["SRT", "VTT", "Original (sans conversion)"]

# Limiteur de vitesse : (octets/sec, libellé). 0 = illimité.
RATELIMIT_PRESETS = [
    (0,                "Illimité"),
    (256 * 1024,       "256 Ko/s"),
    (512 * 1024,       "512 Ko/s"),
    (1 * 1024 * 1024,  "1 Mo/s"),
    (2 * 1024 * 1024,  "2 Mo/s"),
    (5 * 1024 * 1024,  "5 Mo/s"),
    (10 * 1024 * 1024, "10 Mo/s"),
]
RATELIMIT_VALUES = [v for v, _ in RATELIMIT_PRESETS]
RATELIMIT_LABELS = [l for _, l in RATELIMIT_PRESETS]


class SettingsDialog(wx.Dialog):
    """
    Dialogue de préférences — 5 onglets.
    100 % accessible NVDA : labels associés, ordre Tab logique,
    focus sur le premier contrôle à l'ouverture.
    """

    def __init__(self, parent, settings: dict):
        super().__init__(
            parent,
            title="Préférences — DownAccess",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self._settings = dict(settings)  # copie de travail
        self._build_ui()
        self._load_values()
        self._bind_events()
        self.SetMinSize((540, 420))
        self.Fit()
        self.CentreOnParent()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        self.notebook = wx.Notebook(self)
        self.notebook.SetName("Onglets de préférences")

        self._page_general   = self._build_page_general()
        self._page_formats   = self._build_page_formats()
        self._page_subtitles = self._build_page_subtitles()
        self._page_network   = self._build_page_network()
        self._page_advanced  = self._build_page_advanced()

        self.notebook.AddPage(self._page_general,   "Général")
        self.notebook.AddPage(self._page_formats,   "Formats")
        self.notebook.AddPage(self._page_subtitles, "Sous-titres")
        self.notebook.AddPage(self._page_network,   "Réseau")
        self.notebook.AddPage(self._page_advanced,  "Avancé")

        main_sizer.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 8)

        # Boutons OK / Annuler
        btn_sizer = wx.StdDialogButtonSizer()
        self.btn_ok     = wx.Button(self, wx.ID_OK,     label="Enregistrer")
        self.btn_cancel = wx.Button(self, wx.ID_CANCEL, label="Annuler")
        self.btn_ok.SetDefault()
        btn_sizer.AddButton(self.btn_ok)
        btn_sizer.AddButton(self.btn_cancel)
        btn_sizer.Realize()
        main_sizer.Add(btn_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        self.SetSizer(main_sizer)

        # Focus sur le premier champ du premier onglet
        self.txt_folder.SetFocus()

    # ---- Onglet Général ----

    def _build_page_general(self) -> wx.Panel:
        page = wx.Panel(self.notebook)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Dossier de destination
        lbl_folder = wx.StaticText(page, label="Dossier de destination :")
        row_folder = wx.BoxSizer(wx.HORIZONTAL)
        self.txt_folder = wx.TextCtrl(page, name="Dossier de destination")
        self.btn_browse  = wx.Button(page, label="Parcourir…")
        row_folder.Add(self.txt_folder, 1, wx.EXPAND | wx.RIGHT, 6)
        row_folder.Add(self.btn_browse, 0)

        # Téléchargements simultanés
        lbl_concurrent = wx.StaticText(page, label="Téléchargements simultanés :")
        self.spin_concurrent = wx.SpinCtrl(page, min=1, max=10, initial=2,
                                           name="Téléchargements simultanés")

        # Fragments en parallèle
        lbl_fragments = wx.StaticText(page, label="Fragments en parallèle par téléchargement :")
        self.spin_fragments = wx.SpinCtrl(page, min=1, max=16, initial=1,
                                          name="Fragments en parallèle")
        lbl_fragments_hint = wx.StaticText(
            page,
            label="Accélère le téléchargement en utilisant plusieurs connexions. "
                  "1 = désactivé.",
        )
        lbl_fragments_hint.SetForegroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_GRAYTEXT))

        # Action après téléchargement
        lbl_after = wx.StaticText(page, label="Action après téléchargement :")
        self.chk_open_folder = wx.CheckBox(page,
            label="Ouvrir le dossier de destination quand tout est terminé",
            name="Ouvrir le dossier de destination quand tout est terminé")
        self.chk_organize = wx.CheckBox(page,
            label="Organiser dans des sous-dossiers par site",
            name="Organiser dans des sous-dossiers par site")
        self.chk_organize_playlist = wx.CheckBox(page,
            label="Organiser dans des sous-dossiers par playlist",
            name="Organiser dans des sous-dossiers par playlist")

        # Extraction guidée
        lbl_uge = wx.StaticText(page, label="Extraction guidée :")
        self.chk_intercept_title = wx.CheckBox(page,
            label="Utiliser le titre de la page comme nom de fichier (interception)",
            name="Utiliser le titre de la page comme nom de fichier")

        sizer.Add(lbl_folder,        0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 12)
        sizer.Add(row_folder,        0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 6)
        sizer.Add(lbl_concurrent,    0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 12)
        sizer.Add(self.spin_concurrent, 0, wx.LEFT | wx.RIGHT | wx.TOP, 6)
        sizer.Add(lbl_fragments,     0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 12)
        sizer.Add(self.spin_fragments,  0, wx.LEFT | wx.RIGHT | wx.TOP, 6)
        sizer.Add(lbl_fragments_hint,   0, wx.LEFT | wx.RIGHT | wx.TOP, 4)
        sizer.Add(lbl_after,         0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 12)
        sizer.Add(self.chk_open_folder,       0, wx.LEFT | wx.RIGHT | wx.TOP, 6)
        sizer.Add(self.chk_organize,          0, wx.LEFT | wx.RIGHT | wx.TOP, 6)
        sizer.Add(self.chk_organize_playlist, 0, wx.LEFT | wx.RIGHT | wx.TOP, 4)
        sizer.Add(lbl_uge,                    0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 12)
        sizer.Add(self.chk_intercept_title,   0, wx.LEFT | wx.RIGHT | wx.TOP, 6)

        page.SetSizer(sizer)
        return page

    # ---- Onglet Formats ----

    def _build_page_formats(self) -> wx.Panel:
        page = wx.Panel(self.notebook)
        sizer = wx.BoxSizer(wx.VERTICAL)

        self.choice_post = wx.RadioBox(
            page,
            label="Format par défaut",
            choices=POST_LABELS,
            majorDimension=1,
            style=wx.RA_SPECIFY_COLS,
            name="Format par défaut",
        )

        sizer.Add(self.choice_post, 0, wx.EXPAND | wx.ALL, 12)

        page.SetSizer(sizer)
        return page

    # ---- Onglet Sous-titres ----

    def _build_page_subtitles(self) -> wx.Panel:
        page = wx.Panel(self.notebook)
        sizer = wx.BoxSizer(wx.VERTICAL)

        self.chk_auto_subs = wx.CheckBox(page,
            label="Télécharger automatiquement les sous-titres",
            name="Télécharger automatiquement les sous-titres")

        lbl_langs = wx.StaticText(page, label="Langues préférées (codes séparés par des virgules) :")
        self.txt_langs = wx.TextCtrl(page, name="Langues des sous-titres")
        self.txt_langs.SetHint("fr, en")

        self.choice_subfmt = wx.RadioBox(
            page,
            label="Format des sous-titres",
            choices=SUBTITLE_FORMAT_LABELS,
            majorDimension=1,
            style=wx.RA_SPECIFY_COLS,
            name="Format des sous-titres",
        )

        sizer.Add(self.chk_auto_subs, 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)
        sizer.Add(lbl_langs,          0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 12)
        sizer.Add(self.txt_langs,     0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 6)
        sizer.Add(self.choice_subfmt, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 12)

        page.SetSizer(sizer)
        return page

    # ---- Onglet Réseau ----

    def _build_page_network(self) -> wx.Panel:
        page = wx.Panel(self.notebook)
        sizer = wx.BoxSizer(wx.VERTICAL)

        lbl_proxy_http = wx.StaticText(page, label="Proxy HTTP/HTTPS :")
        self.txt_proxy_http = wx.TextCtrl(page, name="Proxy HTTP")
        self.txt_proxy_http.SetHint("http://proxy:8080")

        lbl_proxy_socks = wx.StaticText(page, label="Proxy SOCKS4/5 :")
        self.txt_proxy_socks = wx.TextCtrl(page, name="Proxy SOCKS")
        self.txt_proxy_socks.SetHint("socks5://127.0.0.1:1080")

        lbl_ua = wx.StaticText(page, label="User-Agent personnalisé (laisser vide = défaut) :")
        self.txt_useragent = wx.TextCtrl(page, name="User-Agent")

        lbl_ratelimit = wx.StaticText(page, label="Limite de vitesse de téléchargement :")
        self.choice_ratelimit = wx.Choice(
            page,
            choices=RATELIMIT_LABELS,
            name="Limite de vitesse de téléchargement",
        )
        self.choice_ratelimit.SetSelection(0)

        # Sites avec cookies
        lbl_cookie_sites = wx.StaticText(
            page,
            label="Sites utilisant les cookies du navigateur :",
        )
        self.lst_cookie_sites = wx.ListBox(page, size=(-1, 80),
                                           name="Sites avec cookies")
        lbl_cookies_hint = wx.StaticText(
            page,
            label="Les sites sont ajoutés automatiquement quand vous utilisez "
                  "\"Réessayer avec les cookies\" après une erreur.",
        )
        lbl_cookies_hint.SetForegroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_GRAYTEXT))
        self.btn_remove_cookie_site = wx.Button(page, label="Supprimer le site sélectionné",
                                                name="Supprimer le site sélectionné")
        self.btn_remove_cookie_site.Bind(wx.EVT_BUTTON, self._on_remove_cookie_site)

        sizer.Add(lbl_proxy_http,      0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 12)
        sizer.Add(self.txt_proxy_http,  0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 6)
        sizer.Add(lbl_proxy_socks,     0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 12)
        sizer.Add(self.txt_proxy_socks, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 6)
        sizer.Add(lbl_ua,              0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 12)
        sizer.Add(self.txt_useragent,   0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 6)
        sizer.Add(lbl_ratelimit,        0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 12)
        sizer.Add(self.choice_ratelimit, 0, wx.LEFT | wx.RIGHT | wx.TOP, 6)
        sizer.Add(lbl_cookie_sites,     0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 12)
        sizer.Add(self.lst_cookie_sites, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 6)
        sizer.Add(lbl_cookies_hint,     0, wx.LEFT | wx.RIGHT | wx.TOP, 4)
        sizer.Add(self.btn_remove_cookie_site, 0, wx.LEFT | wx.RIGHT | wx.TOP, 6)

        page.SetSizer(sizer)
        return page

    # ---- Onglet Avancé ----

    def _build_page_advanced(self) -> wx.Panel:
        page = wx.Panel(self.notebook)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Chemin ffmpeg
        lbl_ffmpeg = wx.StaticText(page, label="Chemin vers ffmpeg :")
        row_ffmpeg = wx.BoxSizer(wx.HORIZONTAL)
        self.txt_ffmpeg = wx.TextCtrl(page, name="Chemin ffmpeg")
        self.txt_ffmpeg.SetHint("ffmpeg")
        self.btn_ffmpeg_browse = wx.Button(page, label="Parcourir…",
                                           name="Parcourir ffmpeg")
        self.btn_ffmpeg_test   = wx.Button(page, label="Tester",
                                           name="Tester ffmpeg")
        row_ffmpeg.Add(self.txt_ffmpeg,       1, wx.EXPAND | wx.RIGHT, 6)
        row_ffmpeg.Add(self.btn_ffmpeg_browse, 0, wx.RIGHT, 4)
        row_ffmpeg.Add(self.btn_ffmpeg_test,   0)

        # Options yt-dlp supplémentaires
        lbl_ytdlp_opts = wx.StaticText(page,
            label="Options yt-dlp supplémentaires (raw, une par ligne) :")
        self.txt_ytdlp_opts = wx.TextCtrl(page,
            style=wx.TE_MULTILINE,
            size=(-1, 80),
            name="Options yt-dlp supplémentaires",
        )
        self.txt_ytdlp_opts.SetHint("--no-playlist\n--restrict-filenames")

        sizer.Add(lbl_ffmpeg,         0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 12)
        sizer.Add(row_ffmpeg,         0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 6)
        sizer.Add(lbl_ytdlp_opts,     0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 12)
        sizer.Add(self.txt_ytdlp_opts, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 6)

        page.SetSizer(sizer)
        return page

    # ------------------------------------------------------------------
    # Chargement / sauvegarde des valeurs
    # ------------------------------------------------------------------

    def _load_values(self) -> None:
        s = self._settings

        # Général
        self.txt_folder.SetValue(s.get("download_folder", ""))
        self.spin_concurrent.SetValue(s.get("max_concurrent_downloads", 2))
        self.spin_fragments.SetValue(s.get("concurrent_fragments", 1))
        self.chk_open_folder.SetValue(s.get("open_folder_when_done", False))
        self.chk_organize.SetValue(s.get("organize_by_site", False))
        self.chk_organize_playlist.SetValue(s.get("organize_by_playlist", False))
        self.chk_intercept_title.SetValue(s.get("intercept_use_page_title", True))

        # Formats
        post = s.get("post_processing", "none")
        idx = POST_CHOICES.index(post) if post in POST_CHOICES else 0
        self.choice_post.SetSelection(idx)

        # Sous-titres
        self.chk_auto_subs.SetValue(s.get("auto_subtitles", False))
        self.txt_langs.SetValue(", ".join(s.get("subtitle_langs", ["fr", "en"])))
        subfmt = s.get("subtitle_format", "srt")
        sfmt_idx = SUBTITLE_FORMAT_CHOICES.index(subfmt) if subfmt in SUBTITLE_FORMAT_CHOICES else 0
        self.choice_subfmt.SetSelection(sfmt_idx)

        # Réseau
        self.txt_proxy_http.SetValue(s.get("proxy_http", ""))
        self.txt_proxy_socks.SetValue(s.get("proxy_socks", ""))
        self.txt_useragent.SetValue(s.get("user_agent", ""))
        rl = s.get("ratelimit_bytes", 0)
        rl_idx = RATELIMIT_VALUES.index(rl) if rl in RATELIMIT_VALUES else 0
        self.choice_ratelimit.SetSelection(rl_idx)

        # Cookies
        # Sites avec cookies
        self.lst_cookie_sites.Clear()
        for site in s.get("cookie_sites", []):
            self.lst_cookie_sites.Append(site)

        # Avancé
        self.txt_ffmpeg.SetValue(s.get("ffmpeg_path", "ffmpeg"))
        self.txt_ytdlp_opts.SetValue("\n".join(s.get("ytdlp_extra_opts", [])))

    def _collect_values(self) -> dict:
        s = dict(self._settings)

        # Général
        s["download_folder"]          = self.txt_folder.GetValue().strip()
        s["max_concurrent_downloads"] = self.spin_concurrent.GetValue()
        s["concurrent_fragments"]     = self.spin_fragments.GetValue()
        s["open_folder_when_done"]    = self.chk_open_folder.GetValue()
        s["organize_by_site"]         = self.chk_organize.GetValue()
        s["organize_by_playlist"]     = self.chk_organize_playlist.GetValue()
        s["intercept_use_page_title"] = self.chk_intercept_title.GetValue()

        # Formats
        s["post_processing"] = POST_CHOICES[self.choice_post.GetSelection()]

        # Sous-titres
        s["auto_subtitles"]  = self.chk_auto_subs.GetValue()
        langs_raw = self.txt_langs.GetValue()
        s["subtitle_langs"]  = [l.strip() for l in langs_raw.split(",") if l.strip()]
        s["subtitle_format"] = SUBTITLE_FORMAT_CHOICES[self.choice_subfmt.GetSelection()]

        # Réseau
        s["proxy_http"]  = self.txt_proxy_http.GetValue().strip()
        s["proxy_socks"] = self.txt_proxy_socks.GetValue().strip()
        s["user_agent"]  = self.txt_useragent.GetValue().strip()
        s["ratelimit_bytes"] = RATELIMIT_VALUES[self.choice_ratelimit.GetSelection()]

        # Sites avec cookies
        s["cookie_sites"] = [self.lst_cookie_sites.GetString(i)
                             for i in range(self.lst_cookie_sites.GetCount())]

        # Avancé
        s["ffmpeg_path"] = self.txt_ffmpeg.GetValue().strip() or "ffmpeg"
        opts_raw = self.txt_ytdlp_opts.GetValue()
        s["ytdlp_extra_opts"] = [l.strip() for l in opts_raw.splitlines() if l.strip()]

        return s

    # ------------------------------------------------------------------
    # Événements
    # ------------------------------------------------------------------

    def _bind_events(self) -> None:
        self.btn_ok.Bind(wx.EVT_BUTTON,     self._on_ok)
        self.btn_browse.Bind(wx.EVT_BUTTON, self._on_browse_folder)
        self.btn_ffmpeg_browse.Bind(wx.EVT_BUTTON, self._on_browse_ffmpeg)
        self.btn_ffmpeg_test.Bind(wx.EVT_BUTTON,   self._on_test_ffmpeg)

    def _on_remove_cookie_site(self, _event) -> None:
        sel = self.lst_cookie_sites.GetSelection()
        if sel == wx.NOT_FOUND:
            wx.MessageBox(
                "Sélectionnez un site à supprimer.",
                "Aucune sélection", wx.OK | wx.ICON_INFORMATION, self,
            )
            return
        self.lst_cookie_sites.Delete(sel)

    def _on_ok(self, _event) -> None:
        s = self._collect_values()
        if not s.get("download_folder"):
            wx.MessageBox(
                "Le dossier de destination ne peut pas être vide.",
                "Champ requis", wx.OK | wx.ICON_WARNING, self,
            )
            self.notebook.SetSelection(0)
            self.txt_folder.SetFocus()
            return
        self._settings = s
        self.EndModal(wx.ID_OK)

    def _on_browse_folder(self, _event) -> None:
        current = self.txt_folder.GetValue()
        with wx.DirDialog(
            self,
            "Choisir le dossier de destination",
            defaultPath=current,
            style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST,
        ) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                self.txt_folder.SetValue(dlg.GetPath())

    def _on_browse_ffmpeg(self, _event) -> None:
        with wx.FileDialog(
            self,
            "Chemin vers ffmpeg",
            wildcard="Exécutable (*.exe)|*.exe|Tous les fichiers|*",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                self.txt_ffmpeg.SetValue(dlg.GetPath())

    def _on_test_ffmpeg(self, _event) -> None:
        path = get_ffmpeg_path({"ffmpeg_path": self.txt_ffmpeg.GetValue().strip()})
        try:
            result = subprocess.run(
                [path, "-version"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                first_line = result.stdout.splitlines()[0] if result.stdout else "OK"
                speech.speak("ffmpeg trouvé.")
                wx.MessageBox(
                    f"ffmpeg trouvé :\n{first_line}",
                    "Test ffmpeg réussi", wx.OK | wx.ICON_INFORMATION, self,
                )
            else:
                speech.speak("Test ffmpeg échoué.")
                wx.MessageBox(
                    f"ffmpeg a retourné une erreur :\n{result.stderr[:200]}",
                    "Test ffmpeg échoué", wx.OK | wx.ICON_ERROR, self,
                )
        except FileNotFoundError:
            speech.speak("ffmpeg introuvable.")
            wx.MessageBox(
                f"ffmpeg introuvable à : {path}\n\n"
                "Vérifiez le chemin ou installez ffmpeg.",
                "ffmpeg non trouvé", wx.OK | wx.ICON_ERROR, self,
            )
        except Exception as exc:
            wx.MessageBox(str(exc), "Erreur", wx.OK | wx.ICON_ERROR, self)

    # ------------------------------------------------------------------
    # API publique
    # ------------------------------------------------------------------

    def get_settings(self) -> dict:
        """Retourne le dict de settings modifié (après OK)."""
        return self._settings
