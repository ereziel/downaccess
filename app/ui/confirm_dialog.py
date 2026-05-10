"""Dialogue de confirmation avec case « ne plus demander » mémorisée.

Pattern : un avertissement à montrer une fois, puis l'utilisateur peut le faire
taire. Les avertissements supprimés sont stockés par clé dans
`settings["suppressed_warnings"]` et peuvent être ré-activés depuis les
préférences.
"""
import wx

from app.core import settings as cfg


class ConfirmDialog(wx.Dialog):
    """Dialogue OK/Annuler avec un wx.CheckBox « Ne plus afficher »."""

    def __init__(self, parent, message: str, title: str = "Confirmation"):
        super().__init__(
            parent,
            title=title,
            style=wx.DEFAULT_DIALOG_STYLE,
        )
        self._build_ui(message)
        self.SetMinSize((460, -1))
        self.Fit()
        self.CentreOnParent()
        self.btn_ok.SetFocus()

    def _build_ui(self, message: str) -> None:
        sizer = wx.BoxSizer(wx.VERTICAL)

        lbl_msg = wx.StaticText(self, label=message)
        lbl_msg.Wrap(420)
        sizer.Add(lbl_msg, 0, wx.EXPAND | wx.ALL, 12)

        self.chk_dont_ask = wx.CheckBox(
            self,
            label="Ne plus afficher cet avertissement",
            name="Ne plus afficher cet avertissement",
        )
        sizer.Add(self.chk_dont_ask, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)

        btn_sizer = wx.StdDialogButtonSizer()
        self.btn_ok     = wx.Button(self, wx.ID_OK,     label="Continuer")
        self.btn_cancel = wx.Button(self, wx.ID_CANCEL, label="Annuler")
        self.btn_ok.SetDefault()
        btn_sizer.AddButton(self.btn_ok)
        btn_sizer.AddButton(self.btn_cancel)
        btn_sizer.Realize()
        sizer.Add(btn_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)

        self.SetSizer(sizer)

    def dont_ask_again(self) -> bool:
        return self.chk_dont_ask.GetValue()


def confirm_with_memory(parent, settings: dict, key: str,
                         message: str, title: str = "Confirmation") -> bool:
    """Affiche le dialogue, sauf si la clé `key` est déjà dans
    settings["suppressed_warnings"]. Retourne True si l'utilisateur confirme
    (ou si l'avertissement est supprimé), False s'il annule.

    Si l'utilisateur coche « Ne plus afficher », `key` est ajoutée à la liste
    et `cfg.save(settings)` est appelé pour persister.
    """
    suppressed = settings.get("suppressed_warnings") or []
    if key in suppressed:
        return True

    dlg = ConfirmDialog(parent, message, title)
    try:
        confirmed = dlg.ShowModal() == wx.ID_OK
        if confirmed and dlg.dont_ask_again():
            if key not in suppressed:
                suppressed = list(suppressed) + [key]
                settings["suppressed_warnings"] = suppressed
                cfg.save(settings)
        return confirmed
    finally:
        dlg.Destroy()
