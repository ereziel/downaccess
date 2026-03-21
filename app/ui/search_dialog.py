"""
SearchDialog — saisie de la recherche
SearchResultsDialog — sélection des résultats
"""
import threading

import wx

from app.core import speech

# Sites supportés : (label affiché, préfixe yt-dlp)
_SITES = [
    ("YouTube",    "ytsearch"),
    ("SoundCloud", "scsearch"),
    ("Bilibili",   "bilisearch"),
]


class SearchDialog(wx.Dialog):
    """Saisie de la requête de recherche."""

    def __init__(self, parent):
        super().__init__(parent, title="Rechercher des médias", style=wx.DEFAULT_DIALOG_STYLE)
        self._build_ui()
        self.txt_query.SetFocus()
        speech.speak(
            "Recherche. Saisissez votre requête, choisissez le site et le nombre de résultats."
        )

    def _build_ui(self) -> None:
        sizer = wx.BoxSizer(wx.VERTICAL)
        grid = wx.FlexGridSizer(cols=2, vgap=8, hgap=8)
        grid.AddGrowableCol(1)

        # Requête
        lbl_q = wx.StaticText(self, label="Recherche :")
        self.txt_query = wx.TextCtrl(self, name="Requête de recherche", style=wx.TE_PROCESS_ENTER)
        self.txt_query.Bind(wx.EVT_TEXT_ENTER, self._on_ok)
        grid.Add(lbl_q, 0, wx.ALIGN_CENTER_VERTICAL)
        grid.Add(self.txt_query, 1, wx.EXPAND)

        # Site
        lbl_site = wx.StaticText(self, label="Site :")
        self.choice_site = wx.Choice(
            self,
            choices=[s[0] for s in _SITES],
            name="Site de recherche",
        )
        self.choice_site.SetSelection(0)
        grid.Add(lbl_site, 0, wx.ALIGN_CENTER_VERTICAL)
        grid.Add(self.choice_site, 1, wx.EXPAND)

        # Nombre de résultats
        lbl_n = wx.StaticText(self, label="Résultats :")
        self.spin_n = wx.SpinCtrl(
            self, min=1, max=25, initial=8,
            name="Nombre de résultats",
        )
        grid.Add(lbl_n, 0, wx.ALIGN_CENTER_VERTICAL)
        grid.Add(self.spin_n, 0)

        sizer.Add(grid, 0, wx.EXPAND | wx.ALL, 12)
        sizer.Add(self.CreateButtonSizer(wx.OK | wx.CANCEL), 0, wx.EXPAND | wx.ALL, 8)
        self.SetSizerAndFit(sizer)
        self.Centre()

        self.Bind(wx.EVT_BUTTON, self._on_ok, id=wx.ID_OK)

    def _on_ok(self, _event) -> None:
        if not self.txt_query.GetValue().strip():
            speech.speak("Veuillez saisir une requête.")
            return
        self.EndModal(wx.ID_OK)

    def get_query(self) -> str:
        return self.txt_query.GetValue().strip()

    def get_site_prefix(self) -> str:
        return _SITES[self.choice_site.GetSelection()][1]

    def get_site_label(self) -> str:
        return _SITES[self.choice_site.GetSelection()][0]

    def get_n(self) -> int:
        return self.spin_n.GetValue()


class SearchResultsDialog(wx.Dialog):
    """
    Affiche les résultats de recherche dans une ListCtrl avec cases à cocher.
    L'utilisateur sélectionne puis clique Télécharger.
    """

    def __init__(self, parent, site_label: str, results: list[dict]):
        super().__init__(
            parent,
            title=f"Résultats — {site_label}",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
            size=(820, 480),
        )
        self._results = results
        self._build_ui(site_label)
        self._populate()
        self.lst.SetFocus()
        n = len(results)
        speech.speak(
            f"{n} résultat{'s' if n > 1 else ''} trouvé{'s' if n > 1 else ''}. "
            "Utilisez les flèches pour naviguer, Espace pour cocher."
        )

    def _build_ui(self, site_label: str) -> None:
        sizer = wx.BoxSizer(wx.VERTICAL)

        lbl = wx.StaticText(self, label=f"Résultats de recherche — {site_label} :")
        sizer.Add(lbl, 0, wx.LEFT | wx.TOP | wx.RIGHT, 10)

        self.lst = wx.ListCtrl(
            self,
            style=wx.LC_REPORT | wx.LC_HRULES | wx.BORDER_SUNKEN,
            name="Liste des résultats",
        )
        self.lst.EnableCheckBoxes()
        self.lst.InsertColumn(0, "Titre",   width=420)
        self.lst.InsertColumn(1, "Durée",   width=80)
        self.lst.InsertColumn(2, "Auteur",  width=200)
        sizer.Add(self.lst, 1, wx.EXPAND | wx.ALL, 8)

        # Compteur de sélection
        self.lbl_count = wx.StaticText(self, label="0 sélectionné(s)")
        sizer.Add(self.lbl_count, 0, wx.LEFT | wx.BOTTOM, 10)

        # Format
        fmt_sizer = wx.BoxSizer(wx.HORIZONTAL)
        lbl_fmt = wx.StaticText(self, label="Format :")
        self.choice_fmt = wx.Choice(
            self,
            choices=["Auto", "MP4", "MP3", "M4A"],
            name="Format de téléchargement",
        )
        self.choice_fmt.SetSelection(0)
        fmt_sizer.Add(lbl_fmt, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        fmt_sizer.Add(self.choice_fmt, 0)
        sizer.Add(fmt_sizer, 0, wx.LEFT | wx.BOTTOM, 10)

        # Boutons
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_all   = wx.Button(self, label="Tout sélectionner",   name="Tout sélectionner")
        self.btn_none  = wx.Button(self, label="Tout désélectionner", name="Tout désélectionner")
        self.btn_dl    = wx.Button(self, wx.ID_OK, label="Télécharger la sélection")
        self.btn_close = wx.Button(self, wx.ID_CANCEL, label="Fermer")
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
        self.btn_all.Bind(wx.EVT_BUTTON,  self._on_select_all)
        self.btn_none.Bind(wx.EVT_BUTTON, self._on_select_none)
        self.Bind(wx.EVT_BUTTON, self._on_download, id=wx.ID_OK)

    def _populate(self) -> None:
        for entry in self._results:
            title    = entry.get("title") or entry.get("id") or "?"
            duration = _fmt_duration(entry.get("duration"))
            uploader = entry.get("uploader") or entry.get("channel") or "—"
            idx = self.lst.GetItemCount()
            self.lst.InsertItem(idx, title)
            self.lst.SetItem(idx, 1, duration)
            self.lst.SetItem(idx, 2, uploader)

    def _on_check(self, _event) -> None:
        n = sum(
            1 for i in range(self.lst.GetItemCount())
            if self.lst.IsItemChecked(i)
        )
        self.lbl_count.SetLabel(f"{n} sélectionné(s)")
        speech.speak(f"{n} sélectionné.", interrupt=False)

    def _on_select_all(self, _event) -> None:
        for i in range(self.lst.GetItemCount()):
            self.lst.CheckItem(i, True)
        self._on_check(None)

    def _on_select_none(self, _event) -> None:
        for i in range(self.lst.GetItemCount()):
            self.lst.CheckItem(i, False)
        self._on_check(None)

    def _on_download(self, _event) -> None:
        if not self.get_selected_entries():
            speech.speak("Aucun résultat sélectionné.")
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
