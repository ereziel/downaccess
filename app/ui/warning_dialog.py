"""
Dialogue d'avertissement : le téléchargement a réussi mais avec des erreurs
partielles (ex. sous-titres inaccessibles). Propose d'envoyer un rapport.
"""
import wx


class WarningDialog(wx.Dialog):
    """
    Affiche un avertissement non-bloquant et propose deux actions :
    - Fermer (défaut)
    - Envoyer un rapport
    """

    def __init__(self, parent, message: str):
        super().__init__(
            parent,
            title="Avertissement",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
            size=(520, 300),
        )
        self._send = False
        self._build_ui(message)
        self.btn_close.SetFocus()
        self.Centre()

    def _build_ui(self, message: str) -> None:
        sizer = wx.BoxSizer(wx.VERTICAL)

        lbl = wx.StaticText(
            self,
            label="Le fichier a été téléchargé, mais une erreur s'est produite :",
        )
        sizer.Add(lbl, 0, wx.ALL, 12)

        self.txt_msg = wx.TextCtrl(
            self,
            value=message,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
            name="Message d'avertissement",
        )
        sizer.Add(self.txt_msg, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_close  = wx.Button(self, wx.ID_OK,   label="Fermer",
                                    name="Fermer")
        self.btn_report = wx.Button(self, wx.ID_HELP, label="Envoyer un rapport",
                                    name="Envoyer un rapport")
        btn_sizer.AddStretchSpacer()
        btn_sizer.Add(self.btn_close,  0, wx.RIGHT, 8)
        btn_sizer.Add(self.btn_report, 0, wx.RIGHT, 8)
        sizer.Add(btn_sizer, 0, wx.EXPAND | wx.BOTTOM, 10)

        self.btn_close.Bind(wx.EVT_BUTTON,  self._on_close)
        self.btn_report.Bind(wx.EVT_BUTTON, self._on_report)

        self.SetSizer(sizer)

    def _on_close(self, _event) -> None:
        self._send = False
        self.EndModal(wx.ID_OK)

    def _on_report(self, _event) -> None:
        self._send = True
        self.EndModal(wx.ID_HELP)

    def wants_report(self) -> bool:
        return self._send
