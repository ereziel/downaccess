"""
Dialogue de mise à jour de DownAccess.
Affiche la nouvelle version, les notes de release et propose de mettre à jour.
"""
import wx
from app.core import speech


class UpdateDialog(wx.Dialog):
    """
    Dialogue affiché quand une nouvelle version est disponible.
    Boutons : Mettre à jour maintenant / Plus tard
    """

    def __init__(self, parent, new_version: str, release_notes: str):
        super().__init__(
            parent,
            title=f"Mise à jour disponible — DownAccess {new_version}",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
            size=(560, 420),
        )
        self._build_ui(new_version, release_notes)
        self.txt_notes.SetFocus()
        speech.speak(
            f"Mise à jour disponible. DownAccess {new_version} est disponible. "
            f"Appuyez sur Entrée pour mettre à jour maintenant, ou Échap pour plus tard."
        )

    def _build_ui(self, new_version: str, release_notes: str) -> None:
        sizer = wx.BoxSizer(wx.VERTICAL)

        # En-tête
        lbl_title = wx.StaticText(
            self,
            label=f"DownAccess {new_version} est disponible !",
        )
        font = lbl_title.GetFont()
        font.SetPointSize(font.GetPointSize() + 2)
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        lbl_title.SetFont(font)
        sizer.Add(lbl_title, 0, wx.ALL, 12)

        # Notes de release
        lbl_notes = wx.StaticText(self, label="Notes de version :")
        sizer.Add(lbl_notes, 0, wx.LEFT | wx.RIGHT, 12)

        self.txt_notes = wx.TextCtrl(
            self,
            value=release_notes or "Aucune note disponible.",
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
            name="Notes de version",
        )
        sizer.Add(self.txt_notes, 1, wx.EXPAND | wx.ALL, 8)

        # Boutons
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_update = wx.Button(
            self, wx.ID_OK,
            label="Mettre à jour maintenant",
            name="Mettre à jour maintenant",
        )
        self.btn_later = wx.Button(
            self, wx.ID_CANCEL,
            label="Plus tard",
            name="Reporter la mise à jour",
        )
        btn_sizer.AddStretchSpacer()
        btn_sizer.Add(self.btn_update, 0, wx.RIGHT, 8)
        btn_sizer.Add(self.btn_later,  0, wx.RIGHT, 8)
        sizer.Add(btn_sizer, 0, wx.EXPAND | wx.BOTTOM, 10)

        self.SetSizer(sizer)
        self.Centre()
