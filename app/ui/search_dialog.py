"""
SearchDialog — saisie de la recherche
SearchResultsDialog — sélection des résultats
"""
import wx

from app.core import speech
from app.ui.player_dialog import PlayerDialog

# Sites supportés : (label affiché, clé interne).
# Clés yt-dlp (ytsearch/scsearch) = préfixe de recherche yt-dlp.
# Clés site (francetv/arte) = API HTTP dédiée (cf. app/core/site_search.py).
_SITES = [
    ("YouTube",    "ytsearch"),
    ("SoundCloud", "scsearch"),
    ("france.tv",  "francetv"),
    ("Arte",       "arte"),
]


def _search_types() -> list[tuple[str, str]]:
    """Types de résultat filtrables : (libellé affiché, code interne).

    Construits paresseusement pour que `_()` soit installé au moment de l'appel.
    Seul YouTube gère le filtre par type ; SoundCloud ne renvoie que des pistes.
    """
    return [
        (_("Tous types"), "all"),
        (_("Vidéos"),     "video"),
        (_("Playlists"),  "playlist"),
        (_("Chaînes"),    "channel"),
    ]


def _dl_type_label(code: str) -> str:
    """Convertit le code interne ('video' / 'track' / 'playlist' / 'channel')
    vers son libelle localise pour l'affichage dans la liste de resultats."""
    if code == "track":
        return _("Piste")
    if code == "playlist":
        return _("Playlist")
    if code == "channel":
        return _("Chaîne")
    return _("Vidéo")


class SearchDialog(wx.Dialog):
    """Saisie de la requête de recherche."""

    def __init__(self, parent):
        super().__init__(parent, title=_("Rechercher des médias"), style=wx.DEFAULT_DIALOG_STYLE)
        self._build_ui()
        self.txt_query.SetFocus()
        speech.speak(
            _("Fenêtre de recherche. Saisissez votre requête, choisissez le site, le type et le nombre de résultats.")
        )

    def _build_ui(self) -> None:
        sizer = wx.BoxSizer(wx.VERTICAL)
        grid = wx.FlexGridSizer(cols=2, vgap=8, hgap=8)
        grid.AddGrowableCol(1)

        # Requête
        lbl_q = wx.StaticText(self, label=_("Recherche :"))
        self.txt_query = wx.TextCtrl(self, name=_("Requête de recherche"), style=wx.TE_PROCESS_ENTER)
        self.txt_query.Bind(wx.EVT_TEXT_ENTER, self._on_ok)
        grid.Add(lbl_q, 0, wx.ALIGN_CENTER_VERTICAL)
        grid.Add(self.txt_query, 1, wx.EXPAND)

        # Site
        lbl_site = wx.StaticText(self, label=_("Site :"))
        self.choice_site = wx.Choice(
            self,
            choices=[s[0] for s in _SITES],
            name=_("Site de recherche"),
        )
        self.choice_site.SetSelection(0)
        self.choice_site.Bind(wx.EVT_CHOICE, self._on_site_change)
        grid.Add(lbl_site, 0, wx.ALIGN_CENTER_VERTICAL)
        grid.Add(self.choice_site, 1, wx.EXPAND)

        # Type de résultat (YouTube uniquement)
        lbl_type = wx.StaticText(self, label=_("Type :"))
        self.choice_type = wx.Choice(
            self,
            choices=[t[0] for t in _search_types()],
            name=_("Type de résultat"),
        )
        self.choice_type.SetSelection(0)
        grid.Add(lbl_type, 0, wx.ALIGN_CENTER_VERTICAL)
        grid.Add(self.choice_type, 1, wx.EXPAND)

        # Nombre de résultats
        lbl_n = wx.StaticText(self, label=_("Résultats :"))
        self.spin_n = wx.SpinCtrl(
            self, min=1, max=25, initial=8,
            name=_("Nombre de résultats"),
        )
        grid.Add(lbl_n, 0, wx.ALIGN_CENTER_VERTICAL)
        grid.Add(self.spin_n, 0)

        sizer.Add(grid, 0, wx.EXPAND | wx.ALL, 12)
        sizer.Add(self.CreateButtonSizer(wx.OK | wx.CANCEL), 0, wx.EXPAND | wx.ALL, 8)
        self.SetSizerAndFit(sizer)
        self.Centre()

        self.Bind(wx.EVT_BUTTON, self._on_ok, id=wx.ID_OK)

    def _on_site_change(self, _event) -> None:
        """SoundCloud ne renvoie que des pistes : le filtre de type est sans objet."""
        is_youtube = self.get_site_prefix() == "ytsearch"
        if not is_youtube:
            self.choice_type.SetSelection(0)
        self.choice_type.Enable(is_youtube)

    def _on_ok(self, _event) -> None:
        if not self.txt_query.GetValue().strip():
            speech.speak(_("Veuillez saisir une requête."))
            return
        self.EndModal(wx.ID_OK)

    def get_query(self) -> str:
        return self.txt_query.GetValue().strip()

    def get_site_prefix(self) -> str:
        return _SITES[self.choice_site.GetSelection()][1]

    def get_site_label(self) -> str:
        return _SITES[self.choice_site.GetSelection()][0]

    def get_search_type(self) -> str:
        if not self.choice_type.IsEnabled():
            return "all"
        return _search_types()[self.choice_type.GetSelection()][1]

    def get_n(self) -> int:
        return self.spin_n.GetValue()


# Etats de coche affiches dans la colonne 0 — internes ET visibles.
# Stockes ici pour referer leur valeur courante apres traduction.
def _checked_label() -> str:
    return _("Coché")


def _unchecked_label() -> str:
    return _("Non coché")


class SearchResultsDialog(wx.Dialog):
    """
    Affiche les résultats de recherche dans une ListCtrl avec cases à cocher.
    L'utilisateur sélectionne puis clique Télécharger.
    """

    def __init__(self, parent, site_label: str, results: list[dict],
                 settings: dict | None = None):
        super().__init__(
            parent,
            title=_("Résultats — {site}").format(site=site_label),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
            size=(820, 480),
        )
        self._results = results
        self._settings = settings or {}
        self._build_ui(site_label)
        self._populate()
        self.Bind(wx.EVT_CLOSE, self._on_close)
        self.Bind(wx.EVT_WINDOW_DESTROY, self._on_destroy)
        self.lst.SetFocus()
        n = len(results)
        if n > 1:
            count_msg = _("{count} résultats trouvés.").format(count=n)
        else:
            count_msg = _("{count} résultat trouvé.").format(count=n)
        speech.speak(
            count_msg + " "
            + _("Utilisez les flèches pour naviguer, Espace pour cocher, Entrée pour l'aperçu.")
        )

    def _build_ui(self, site_label: str) -> None:
        sizer = wx.BoxSizer(wx.VERTICAL)

        lbl = wx.StaticText(
            self,
            label=_("Résultats de recherche — {site} :").format(site=site_label),
        )
        sizer.Add(lbl, 0, wx.LEFT | wx.TOP | wx.RIGHT, 10)

        self.lst = wx.ListCtrl(
            self,
            style=wx.LC_REPORT | wx.LC_HRULES | wx.BORDER_SUNKEN,
            name=_("Liste des résultats"),
        )
        self.lst.EnableCheckBoxes()
        self.lst.InsertColumn(0, _("Sélection"), width=100)
        self.lst.InsertColumn(1, _("Titre"),     width=360)
        self.lst.InsertColumn(2, _("Durée"),     width=80)
        self.lst.InsertColumn(3, _("Auteur"),    width=180)
        self.lst.InsertColumn(4, _("Type"),      width=80)
        sizer.Add(self.lst, 1, wx.EXPAND | wx.ALL, 8)

        # Compteur de sélection
        self.lbl_count = wx.StaticText(self, label=_("0 sélectionné(s)"))
        sizer.Add(self.lbl_count, 0, wx.LEFT | wx.BOTTOM, 10)

        # Format
        fmt_sizer = wx.BoxSizer(wx.HORIZONTAL)
        lbl_fmt = wx.StaticText(self, label=_("Format :"))
        self.choice_fmt = wx.Choice(
            self,
            choices=[_("Auto"), "MP4", "MP3", "M4A"],
            name=_("Format de téléchargement"),
        )
        self.choice_fmt.SetSelection(0)
        fmt_sizer.Add(lbl_fmt, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        fmt_sizer.Add(self.choice_fmt, 0)
        sizer.Add(fmt_sizer, 0, wx.LEFT | wx.BOTTOM, 10)

        # Boutons
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_preview = wx.Button(self, label=_("Aperçu"), name=_("Aperçu"))
        self.btn_all   = wx.Button(self, label=_("Tout sélectionner"),   name=_("Tout sélectionner"))
        self.btn_none  = wx.Button(self, label=_("Tout désélectionner"), name=_("Tout désélectionner"))
        self.btn_dl    = wx.Button(self, wx.ID_OK, label=_("Télécharger la sélection"))
        self.btn_close = wx.Button(self, wx.ID_CANCEL, label=_("Fermer"))
        btn_sizer.Add(self.btn_preview, 0, wx.RIGHT, 6)
        btn_sizer.Add(self.btn_all,   0, wx.RIGHT, 6)
        btn_sizer.Add(self.btn_none,  0, wx.RIGHT, 6)
        btn_sizer.AddStretchSpacer()
        btn_sizer.Add(self.btn_dl,    0, wx.RIGHT, 6)
        btn_sizer.Add(self.btn_close, 0)
        sizer.Add(btn_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        self.SetSizer(sizer)
        self.Centre()

        self.lst.Bind(wx.EVT_LIST_ITEM_CHECKED,   self._on_check)
        self.lst.Bind(wx.EVT_LIST_ITEM_UNCHECKED, self._on_check)
        self.lst.Bind(wx.EVT_KEY_DOWN, self._on_list_key)
        self.lst.Bind(wx.EVT_LEFT_DCLICK, self._on_preview)
        self.btn_preview.Bind(wx.EVT_BUTTON, self._on_preview)
        self.btn_all.Bind(wx.EVT_BUTTON,  self._on_select_all)
        self.btn_none.Bind(wx.EVT_BUTTON, self._on_select_none)
        self.Bind(wx.EVT_BUTTON, self._on_download, id=wx.ID_OK)
        self.Bind(wx.EVT_BUTTON, self._on_cancel,   id=wx.ID_CANCEL)

    def _populate(self) -> None:
        for entry in self._results:
            title    = entry.get("title") or entry.get("id") or "?"
            if entry.get("_has_ad"):
                # Signale aux utilisateurs deficients visuels que l'audiodescription
                # existe (lu par NVDA dans le titre).
                title = _("{title} — Audiodescription").format(title=title)
            duration = _fmt_duration(entry.get("duration"))
            uploader = entry.get("uploader") or entry.get("channel") or "—"
            entry_type = entry.get("_dl_type") or "video"
            idx = self.lst.GetItemCount()
            self.lst.InsertItem(idx, _unchecked_label())
            self.lst.SetItem(idx, 1, title)
            self.lst.SetItem(idx, 2, duration)
            self.lst.SetItem(idx, 3, uploader)
            self.lst.SetItem(idx, 4, _dl_type_label(entry_type))

    def _on_check(self, event) -> None:
        idx = event.GetIndex() if event else -1
        checked = False
        if idx >= 0:
            checked = self.lst.IsItemChecked(idx)
            self.lst.SetItem(idx, 0, _checked_label() if checked else _unchecked_label())
        n = sum(
            1 for i in range(self.lst.GetItemCount())
            if self.lst.IsItemChecked(i)
        )
        if n > 1:
            self.lbl_count.SetLabel(_("{count} sélectionnés").format(count=n))
            count_msg = _("{count} sélectionnés.").format(count=n)
        else:
            self.lbl_count.SetLabel(_("{count} sélectionné").format(count=n))
            count_msg = _("{count} sélectionné.").format(count=n)
        if idx >= 0:
            title = self.lst.GetItemText(idx, 1)
            state = _("coché") if checked else _("non coché")
            speech.speak(
                _("{state}. {title}. {count_msg}").format(
                    state=state, title=title, count_msg=count_msg
                )
            )
        else:
            speech.speak(count_msg)

    def _on_select_all(self, _event) -> None:
        for i in range(self.lst.GetItemCount()):
            self.lst.CheckItem(i, True)
            self.lst.SetItem(i, 0, _checked_label())
        self._on_check(None)

    def _on_select_none(self, _event) -> None:
        for i in range(self.lst.GetItemCount()):
            self.lst.CheckItem(i, False)
            self.lst.SetItem(i, 0, _unchecked_label())
        self._on_check(None)

    # -- Clavier liste --------------------------------------------------

    def _on_list_key(self, event):
        """Entrée → aperçu ; autres touches → comportement natif."""
        if event.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self._on_preview(None)
        else:
            event.Skip()

    # -- Aperçu audio --------------------------------------------------

    def _on_preview(self, _event) -> None:
        """Ouvre la fenêtre player pour le résultat ayant le focus."""
        idx = self.lst.GetFocusedItem()
        if idx < 0:
            speech.speak(_("Sélectionnez un résultat."))
            return
        entry = self._results[idx]
        entry_type = entry.get("_dl_type") or "video"
        if entry_type in ("channel", "playlist"):
            label = _("une chaîne") if entry_type == "channel" else _("une playlist")
            wx.MessageBox(
                _("L'aperçu n'est pas disponible pour {label}.\n\nCochez l'élément et utilisez « Télécharger la sélection » pour récupérer son contenu.").format(label=label),
                _("Aperçu indisponible"),
                wx.OK | wx.ICON_INFORMATION,
                self,
            )
            return
        title = entry.get("title") or entry.get("id") or "?"
        url = self._entry_url(entry)
        if not url:
            return
        dlg = PlayerDialog(self, web_url=url, title=title)
        dlg.ShowModal()
        dlg.Destroy()

    def _entry_url(self, entry: dict) -> str:
        """Reconstruit l'URL web d'une entrée."""
        url = entry.get("webpage_url") or entry.get("url") or ""
        if url.startswith("francetv:"):
            return ""  # schéma interne yt-dlp : pas d'aperçu navigateur possible
        if url and not url.startswith("http"):
            ie_key = (entry.get("ie_key") or entry.get("extractor_key") or "").lower()
            vid_id = entry.get("id", "") or url
            if "youtube" in ie_key or not ie_key:
                url = f"https://www.youtube.com/watch?v={vid_id}"
            else:
                url = ""
        return url

    def _on_close(self, _event) -> None:
        self.EndModal(wx.ID_CANCEL)

    def _on_cancel(self, _event) -> None:
        self.EndModal(wx.ID_CANCEL)

    def _on_destroy(self, event) -> None:
        event.Skip()

    # -- Téléchargement -------------------------------------------------

    def _on_download(self, _event) -> None:
        selected = self.get_selected_entries()
        if not selected:
            msg = _("Veuillez cocher au moins un résultat à télécharger (touche Espace).")
            speech.speak(msg)
            wx.MessageBox(msg, _("Aucune sélection"), wx.OK | wx.ICON_INFORMATION, self)
            return

        bulk_types = {e.get("_dl_type") for e in selected
                      if e.get("_dl_type") in ("channel", "playlist")}
        if bulk_types:
            from app.ui.confirm_dialog import confirm_with_memory
            labels = []
            if "channel" in bulk_types:
                labels.append(_("une chaîne (potentiellement des centaines de vidéos)"))
            if "playlist" in bulk_types:
                labels.append(_("une playlist complète"))
            joined = _(" et ").join(labels)
            if not confirm_with_memory(
                self, self._settings, "search_bulk_download",
                _("Votre sélection contient {labels}.\n\nLe téléchargement peut prendre beaucoup de temps et d'espace disque. Continuer ?").format(labels=joined),
                _("Téléchargement volumineux"),
            ):
                return

        self.EndModal(wx.ID_OK)

    def get_selected_entries(self) -> list[dict]:
        return [
            self._results[i]
            for i in range(self.lst.GetItemCount())
            if self.lst.IsItemChecked(i)
        ]

    def get_format(self) -> str:
        return ["auto", "mp4", "mp3", "m4a"][self.choice_fmt.GetSelection()]


def _fmt_duration(seconds) -> str:
    if not seconds:
        return "—"
    try:
        s = int(seconds)
        h, m = divmod(s, 3600)
        m, s = divmod(m, 60)
        if h:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"
    except Exception:
        return "—"
