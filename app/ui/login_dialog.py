"""
Dialogue de connexion à un site.
Ouvre le navigateur Chrome avec le vrai profil de l'utilisateur
(via DrissionPage) pour que les cookies soient conservés.
yt-dlp y a accès via cookiesfrombrowser.
"""
import logging
import threading

import wx

from app.core import speech
from app.core.browser import find_browser, browser_name

_log = logging.getLogger("downaccess.login")


class LoginDialog(wx.Dialog):
    """
    Dialogue de connexion. Ouvre Chrome avec le vrai profil utilisateur,
    l'utilisateur se connecte, puis ferme ce dialogue.
    Les cookies restent dans le profil Chrome → yt-dlp y accède.
    """

    def __init__(self, parent):
        super().__init__(
            parent,
            title=_("Se connecter à un site — DownAccess"),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
            size=(500, 300),
        )
        self._page = None
        self._build_ui()
        self._bind_events()
        self.Centre()

        speech.speak(
            _(
                "Connexion à un site. "
                "Saisissez l'adresse et connectez-vous dans le navigateur. "
                "Vos cookies seront conservés pour les prochains téléchargements. "
                "Note : les contenus protégés par DRM (Netflix, Disney+, Prime Video) ne sont pas pris en charge."
            ),
        )

    def _build_ui(self) -> None:
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Barre d'adresse
        row = wx.BoxSizer(wx.HORIZONTAL)
        lbl_url = wx.StaticText(panel, label=_("Adresse du site :"))
        self.txt_url = wx.TextCtrl(
            panel,
            style=wx.TE_PROCESS_ENTER,
            name=_("Adresse du site"),
        )
        self.txt_url.SetHint("https://www.youtube.com")
        self.btn_go = wx.Button(panel, label=_("Ouvrir"), name=_("Ouvrir dans le navigateur"))
        row.Add(lbl_url, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        row.Add(self.txt_url, 1, wx.EXPAND | wx.RIGHT, 6)
        row.Add(self.btn_go, 0)
        sizer.Add(row, 0, wx.EXPAND | wx.ALL, 8)

        # Info
        self.lbl_status = wx.StaticText(
            panel,
            label=_(
                "Entrez l'adresse du site et connectez-vous dans le navigateur.\n"
                "Votre vrai profil Chrome est utilisé : vos cookies seront conservés\n"
                "et réutilisés automatiquement pour les téléchargements.\n\n"
                "Note : les contenus protégés par DRM ne sont pas pris en charge."
            ),
        )
        sizer.Add(self.lbl_status, 1, wx.EXPAND | wx.ALL, 8)

        # Boutons
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_clear_cookies = wx.Button(
            panel,
            label=_("Supprimer les cookies du site"),
            name=_("Supprimer les cookies du site actuellement ouvert"),
        )
        self.btn_clear_cookies.Disable()
        self.btn_close = wx.Button(panel, wx.ID_CLOSE, label=_("Fermer"), name=_("Fermer"))
        btn_sizer.Add(self.btn_clear_cookies, 0, wx.RIGHT, 6)
        btn_sizer.AddStretchSpacer()
        btn_sizer.Add(self.btn_close, 0)
        sizer.Add(btn_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        panel.SetSizer(sizer)
        self.txt_url.SetFocus()

    def _bind_events(self) -> None:
        self.txt_url.Bind(wx.EVT_TEXT_ENTER, self._on_go)
        self.btn_go.Bind(wx.EVT_BUTTON, self._on_go)
        self.btn_clear_cookies.Bind(wx.EVT_BUTTON, self._on_clear_cookies)
        self.btn_close.Bind(wx.EVT_BUTTON, lambda _e: self.Close())
        self.Bind(wx.EVT_CLOSE, self._on_close)

    def _on_go(self, _event) -> None:
        url = self.txt_url.GetValue().strip()
        if not url:
            return
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
            self.txt_url.SetValue(url)

        self.lbl_status.SetLabel(_("Ouverture du navigateur…"))
        self.btn_go.Disable()

        def open_browser():
            try:
                bp = find_browser()
                if not bp:
                    wx.CallAfter(self._on_browser_error,
                                 _("Aucun navigateur compatible trouvé.\nInstallez Google Chrome, Microsoft Edge ou Brave."))
                    return
                if self._page is None:
                    from DrissionPage import ChromiumPage, ChromiumOptions
                    co = ChromiumOptions()
                    co.set_browser_path(bp)
                    co.use_system_user_path()
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
        name = getattr(self, "_browser_name", _("Le navigateur"))
        self.lbl_status.SetLabel(
            _(
                "{name} est ouvert sur : {title}\n\n"
                "Connectez-vous dans {name}, puis fermez cette fenêtre.\n"
                "Vos cookies seront conservés pour les prochains téléchargements."
            ).format(name=name, title=title)
        )
        self.btn_go.Enable()
        self.btn_clear_cookies.Enable()
        speech.speak(
            _("{name} est ouvert. Connectez-vous puis fermez cette fenêtre.").format(name=name)
        )

    def _on_browser_error(self, error: str) -> None:
        self.btn_go.Enable()
        self.lbl_status.SetLabel(_("Erreur : {error}").format(error=error))
        wx.MessageBox(
            _("Impossible d'ouvrir le navigateur.\n\n{error}").format(error=error),
            _("Erreur"),
            wx.OK | wx.ICON_ERROR,
            self,
        )

    def _on_clear_cookies(self, _event) -> None:
        """Supprime les cookies du site actuellement ouvert."""
        if not self._page:
            return
        try:
            current_url = self._page.url
            # Extraire le domaine
            from urllib.parse import urlparse
            domain = urlparse(current_url).hostname or ""
            if not domain:
                wx.MessageBox(
                    _("Impossible de déterminer le domaine du site."),
                    _("Erreur"), wx.OK | wx.ICON_WARNING, self,
                )
                return

            confirm = wx.MessageBox(
                _("Supprimer tous les cookies de {domain} ?\n\nVous serez déconnecté de ce site.").format(domain=domain),
                _("Confirmer la suppression"),
                wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION,
                self,
            )
            if confirm != wx.YES:
                return

            # Supprimer les cookies via CDP
            self._page.run_cdp(
                "Network.deleteCookies",
                domain=domain,
                name="",
            )
            # Supprimer aussi avec le point devant (sous-domaines)
            self._page.run_cdp(
                "Network.deleteCookies",
                domain=f".{domain}",
                name="",
            )
            # Recharger la page pour refléter la déconnexion
            self._page.refresh()
            self.lbl_status.SetLabel(
                _("Cookies de {domain} supprimés.\nVous êtes déconnecté de ce site.").format(domain=domain)
            )
            speech.speak(_("Cookies de {domain} supprimés.").format(domain=domain))
        except Exception as exc:
            _log.error("Erreur suppression cookies : %s", exc)
            wx.MessageBox(
                _("Erreur lors de la suppression des cookies :\n{error}").format(error=exc),
                _("Erreur"), wx.OK | wx.ICON_ERROR, self,
            )

    def _on_close(self, event) -> None:
        if self._page:
            try:
                self._page.quit()
            except Exception:
                pass
            self._page = None
        event.Skip()
