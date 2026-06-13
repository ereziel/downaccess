import wx

from app.core import speech


class PlaylistHarvestDialog(wx.Dialog):
    """Dialogue de progression (modeless) pendant la récupération de la liste
    complète d'une playlist via le navigateur.

    Accessible : wx.Gauge déterminée (NVDA annonce la progression) + libellé
    de statut. Un seul bouton « Annuler ». Le parent crée, met à jour
    (`set_progress`) et détruit ce dialogue ; `on_cancel` est appelé quand
    l'utilisateur annule (bouton ou fermeture de la fenêtre).
    """

    def __init__(self, parent, playlist_title: str, total: int, on_cancel):
        super().__init__(
            parent,
            title=_("Récupération de la playlist"),
            style=wx.DEFAULT_DIALOG_STYLE & ~wx.CLOSE_BOX | wx.RESIZE_BORDER,
        )
        self._on_cancel = on_cancel
        self._total = max(int(total or 0), 0)
        self._cancelled = False
        self._last_spoken = 0

        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        intro = wx.StaticText(panel, label=_(
            "Récupération de toutes les vidéos de « {title} » via le navigateur.\n"
            "Cela peut prendre un moment pour les grandes playlists."
        ).format(title=playlist_title))

        self.lbl_status = wx.StaticText(panel, label=self._status_label(0))

        self.gauge = wx.Gauge(
            panel,
            range=self._total or 1,
            style=wx.GA_HORIZONTAL,
            name=_("Progression de la récupération"),
        )

        self.btn_cancel = wx.Button(panel, wx.ID_CANCEL, label=_("Annuler"))

        sizer.Add(intro,           0, wx.EXPAND | wx.ALL, 12)
        sizer.Add(self.lbl_status, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 12)
        sizer.Add(self.gauge,      0, wx.EXPAND | wx.ALL, 12)
        sizer.Add(self.btn_cancel, 0, wx.ALIGN_RIGHT | wx.ALL, 12)
        panel.SetSizer(sizer)

        self.SetMinSize((460, -1))
        self.Fit()
        self.CentreOnParent()

        self.Bind(wx.EVT_BUTTON, self._do_cancel, id=wx.ID_CANCEL)
        self.Bind(wx.EVT_CLOSE, self._do_cancel)
        wx.CallAfter(self.gauge.SetFocus)

    def _status_label(self, n: int) -> str:
        if self._total:
            return _("{n} sur {total} vidéos trouvées…").format(n=n, total=self._total)
        return _("{n} vidéos trouvées…").format(n=n)

    def set_progress(self, n: int) -> None:
        """Met à jour la jauge et le libellé (appelé via wx.CallAfter)."""
        if not self:
            return
        if self._total:
            self.gauge.SetValue(min(n, self._total))
        else:
            self.gauge.Pulse()
        self.lbl_status.SetLabel(self._status_label(n))
        # Jalons vocaux tous les 100 (pas de doublon avec un dialogue visible).
        if n - self._last_spoken >= 100:
            self._last_spoken = n
            speech.speak(self._status_label(n))

    def _do_cancel(self, _event) -> None:
        """Annulation (bouton ou fermeture) : signale au parent et attend que la
        récolte s'arrête (le parent détruira ce dialogue)."""
        if self._cancelled:
            return
        self._cancelled = True
        self.btn_cancel.Disable()
        self.lbl_status.SetLabel(_("Annulation en cours…"))
        self._on_cancel()
