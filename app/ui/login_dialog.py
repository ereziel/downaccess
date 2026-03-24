"""
Dialogue de connexion à un site.
Ouvre un navigateur WebView2 avec profil persistent pour que l'utilisateur
se connecte à un service. Les cookies sont sauvegardés automatiquement
et réutilisés par yt-dlp si l'option est activée dans les préférences.
"""
import os
from pathlib import Path

import wx
import wx.html2

from app.core import speech


class LoginDialog(wx.Frame):
    """
    Navigateur simplifié pour se connecter à un site.
    Partage le même profil WebView2 que l'extraction guidée.
    """

    def __init__(self, parent):
        # Profil WebView2 persistent (partagé avec UGE)
        profile_dir = Path(os.environ.get("APPDATA", "")) / "DownAccess" / "WebView2Profile"
        profile_dir.mkdir(parents=True, exist_ok=True)
        os.environ["WEBVIEW2_USER_DATA_FOLDER"] = str(profile_dir)

        super().__init__(
            parent,
            title="Se connecter à un site — DownAccess",
            style=wx.DEFAULT_FRAME_STYLE,
            size=(1000, 700),
        )

        self._build_ui()
        self._bind_events()
        self.Centre()

        speech.speak(
            "Navigateur de connexion ouvert. "
            "Saisissez l'adresse du site et connectez-vous. "
            "Vos cookies seront sauvegardés automatiquement."
        )

    def _build_ui(self) -> None:
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Barre d'adresse
        row = wx.BoxSizer(wx.HORIZONTAL)
        lbl_url = wx.StaticText(panel, label="Adresse :")
        self.txt_url = wx.TextCtrl(
            panel,
            style=wx.TE_PROCESS_ENTER,
            name="Adresse du site",
        )
        self.btn_go = wx.Button(panel, label="Aller", name="Aller")
        row.Add(lbl_url, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        row.Add(self.txt_url, 1, wx.EXPAND | wx.RIGHT, 6)
        row.Add(self.btn_go, 0)
        sizer.Add(row, 0, wx.EXPAND | wx.ALL, 8)

        # WebView2
        self.browser = wx.html2.WebView.New(panel, name="Navigateur")
        sizer.Add(self.browser, 1, wx.EXPAND)

        # Info
        self.lbl_status = wx.StaticText(
            panel,
            label="Connectez-vous au site. Les cookies seront sauvegardés automatiquement.",
        )
        sizer.Add(self.lbl_status, 0, wx.ALL, 8)

        # Bouton fermer
        self.btn_close = wx.Button(panel, wx.ID_CLOSE, label="Fermer", name="Fermer")
        sizer.Add(self.btn_close, 0, wx.ALIGN_RIGHT | wx.RIGHT | wx.BOTTOM, 8)

        panel.SetSizer(sizer)
        self.txt_url.SetFocus()

    def _bind_events(self) -> None:
        self.txt_url.Bind(wx.EVT_TEXT_ENTER, self._on_navigate)
        self.btn_go.Bind(wx.EVT_BUTTON, self._on_navigate)
        self.btn_close.Bind(wx.EVT_BUTTON, lambda _e: self.Close())
        self.browser.Bind(wx.html2.EVT_WEBVIEW_NAVIGATED, self._on_navigated)

    def _on_navigate(self, _event) -> None:
        url = self.txt_url.GetValue().strip()
        if not url:
            return
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        self.browser.LoadURL(url)
        self.lbl_status.SetLabel("Chargement…")

    def _on_navigated(self, event) -> None:
        url = event.GetURL()
        self.txt_url.SetValue(url)
        self.lbl_status.SetLabel("Page chargée. Connectez-vous si nécessaire.")
