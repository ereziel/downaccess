"""
Dialogue de connexion à un site.
Ouvre un vrai navigateur Chrome (via DrissionPage) pour que l'utilisateur
se connecte à un service. Les cookies sont sauvegardés dans le profil
Chrome par défaut et réutilisés par yt-dlp.
"""
import logging
import threading

import wx

from app.core import speech
from app.core.browser import find_browser, browser_name

_log = logging.getLogger("downaccess.login")


class LoginDialog(wx.Dialog):
    """
    Dialogue de connexion. Ouvre Chrome via DrissionPage,
    l'utilisateur se connecte, puis ferme ce dialogue.
    """

    def __init__(self, parent):
        super().__init__(
            parent,
            title="Se connecter à un site — DownAccess",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
            size=(500, 250),
        )
        self._page = None
        self._build_ui()
        self._bind_events()
        self.Centre()

        speech.speak(
            "Connexion à un site. "
            "Saisissez l'adresse et connectez-vous dans le navigateur. "
            "Note : les contenus protégés par DRM (Netflix, Disney+, Prime Video) ne sont pas pris en charge.",
        )

    def _build_ui(self) -> None:
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Barre d'adresse
        row = wx.BoxSizer(wx.HORIZONTAL)
        lbl_url = wx.StaticText(panel, label="Adresse du site :")
        self.txt_url = wx.TextCtrl(
            panel,
            style=wx.TE_PROCESS_ENTER,
            name="Adresse du site",
        )
        self.txt_url.SetHint("https://www.youtube.com")
        self.btn_go = wx.Button(panel, label="Ouvrir", name="Ouvrir dans le navigateur")
        row.Add(lbl_url, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        row.Add(self.txt_url, 1, wx.EXPAND | wx.RIGHT, 6)
        row.Add(self.btn_go, 0)
        sizer.Add(row, 0, wx.EXPAND | wx.ALL, 8)

        # Info
        self.lbl_status = wx.StaticText(
            panel,
            label="Entrez l'adresse du site et connectez-vous dans le navigateur.\n"
                  "Vos cookies seront sauvegardés automatiquement.\n\n"
                  "Note : les contenus protégés par DRM (Netflix, Disney+, Prime Video) ne sont pas pris en charge.",
        )
        sizer.Add(self.lbl_status, 1, wx.EXPAND | wx.ALL, 8)

        # Bouton fermer
        self.btn_close = wx.Button(panel, wx.ID_CLOSE, label="Fermer", name="Fermer")
        sizer.Add(self.btn_close, 0, wx.ALIGN_RIGHT | wx.RIGHT | wx.BOTTOM, 8)

        panel.SetSizer(sizer)
        self.txt_url.SetFocus()

    def _bind_events(self) -> None:
        self.txt_url.Bind(wx.EVT_TEXT_ENTER, self._on_go)
        self.btn_go.Bind(wx.EVT_BUTTON, self._on_go)
        self.btn_close.Bind(wx.EVT_BUTTON, lambda _e: self.Close())
        self.Bind(wx.EVT_CLOSE, self._on_close)

    def _on_go(self, _event) -> None:
        url = self.txt_url.GetValue().strip()
        if not url:
            return
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
            self.txt_url.SetValue(url)

        self.lbl_status.SetLabel("Ouverture de Chrome...")
        self.btn_go.Disable()

        def open_browser():
            try:
                bp = find_browser()
                if not bp:
                    wx.CallAfter(self._on_browser_error,
                                 "Aucun navigateur compatible trouvé.\n"
                                 "Installez Google Chrome, Microsoft Edge ou Brave.")
                    return
                from DrissionPage import ChromiumPage, ChromiumOptions
                co = ChromiumOptions()
                co.set_browser_path(bp)
                co.auto_port()
                self._page = ChromiumPage(co)
                self._browser_name = browser_name(bp)
                self._page.get(url)
                title = self._page.title
                wx.CallAfter(self._on_browser_ready, title)
            except Exception as exc:
                _log.error("Impossible d'ouvrir le navigateur : %s", exc)
                wx.CallAfter(self._on_browser_error, str(exc))

        threading.Thread(target=open_browser, daemon=True).start()

    def _on_browser_ready(self, title: str) -> None:
        name = getattr(self, "_browser_name", "Le navigateur")
        self.lbl_status.SetLabel(
            f"{name} est ouvert sur : {title}\n\n"
            f"Connectez-vous dans {name}, puis fermez cette fenêtre.\n"
            "Vos cookies seront conservés pour les prochains téléchargements."
        )
        self.btn_go.Enable()
        speech.speak(f"{name} est ouvert. Connectez-vous puis fermez cette fenêtre.")

    def _on_browser_error(self, error: str) -> None:
        self.btn_go.Enable()
        self.lbl_status.SetLabel(f"Erreur : {error}")
        wx.MessageBox(
            f"Impossible d'ouvrir Chrome.\n\n{error}",
            "Erreur",
            wx.OK | wx.ICON_ERROR,
            self,
        )

    def _on_close(self, event) -> None:
        if self._page:
            try:
                self._page.quit()
            except Exception:
                pass
            self._page = None
        event.Skip()
