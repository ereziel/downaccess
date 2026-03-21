"""
Dialogue de rapport d'erreur DownAccess.
Explique le processus de diagnostic, collecte un commentaire utilisateur,
affiche la progression et le résultat de l'envoi.
"""
import wx
from app.core import speech


class ReportDialog(wx.Dialog):
    """
    Étape 1 : présente le formulaire (commentaire + bouton Lancer).
    Étape 2 : affiche "Diagnostic en cours…" pendant le re-run.
    Étape 3 : affiche le résultat (succès ou erreur).
    """

    def __init__(self, parent, url: str, site: str, error_message: str):
        super().__init__(
            parent,
            title="Envoyer un rapport d'erreur",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
            size=(560, 420),
        )
        self._url           = url
        self._site          = site
        self._error_message = error_message
        self._comment       = ""
        self._build_ui()
        self.txt_comment.SetFocus()
        self.Centre()

    # ------------------------------------------------------------------
    # Construction de l'UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self._sizer = wx.BoxSizer(wx.VERTICAL)

        # Explication
        intro = (
            "Pour générer un rapport complet, DownAccess va relancer le "
            "téléchargement en mode diagnostic afin de capturer les logs "
            "détaillés de yt-dlp.\n\n"
            f"URL : {self._url or '—'}\n"
            f"Site : {self._site or '—'}"
        )
        lbl_intro = wx.StaticText(self, label=intro)
        lbl_intro.Wrap(520)
        self._sizer.Add(lbl_intro, 0, wx.ALL, 12)

        # Champ commentaire
        lbl_comment = wx.StaticText(self, label="Commentaire (optionnel) :")
        self._sizer.Add(lbl_comment, 0, wx.LEFT | wx.RIGHT, 12)

        self.txt_comment = wx.TextCtrl(
            self,
            style=wx.TE_MULTILINE,
            name="Commentaire",
        )
        self._sizer.Add(self.txt_comment, 1, wx.EXPAND | wx.ALL, 8)

        # Zone de statut (cachée au départ)
        self.lbl_status = wx.StaticText(self, label="")
        self._sizer.Add(self.lbl_status, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)

        # Boutons
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_send   = wx.Button(self, wx.ID_OK,     label="Lancer le diagnostic et envoyer",
                                    name="Lancer le diagnostic et envoyer")
        self.btn_cancel = wx.Button(self, wx.ID_CANCEL, label="Annuler",
                                    name="Annuler")
        btn_sizer.AddStretchSpacer()
        btn_sizer.Add(self.btn_send,   0, wx.RIGHT, 8)
        btn_sizer.Add(self.btn_cancel, 0, wx.RIGHT, 8)
        self._sizer.Add(btn_sizer, 0, wx.EXPAND | wx.BOTTOM, 10)

        self.btn_send.Bind(wx.EVT_BUTTON, self._on_send)

        self.SetSizer(self._sizer)

    # ------------------------------------------------------------------
    # Transitions d'état
    # ------------------------------------------------------------------

    def set_running(self) -> None:
        """Passe en mode "diagnostic en cours"."""
        self.btn_send.Enable(False)
        self.btn_cancel.Enable(False)
        self.txt_comment.Enable(False)
        self.lbl_status.SetLabel("Diagnostic en cours…")
        speech.speak("Diagnostic en cours.")
        self.Layout()

    def set_done(self, success: bool, message: str) -> None:
        """Affiche le résultat et réactive le bouton Fermer."""
        self.lbl_status.SetLabel(message)
        self.btn_cancel.SetLabel("Fermer")
        self.btn_cancel.Enable(True)
        self.btn_cancel.SetFocus()
        speech.speak(message)
        self.Layout()

    # ------------------------------------------------------------------
    # Accesseurs
    # ------------------------------------------------------------------

    def get_comment(self) -> str:
        return self.txt_comment.GetValue().strip()

    # ------------------------------------------------------------------
    # Événements
    # ------------------------------------------------------------------

    def _on_send(self, _event) -> None:
        self._comment = self.get_comment()
        self.EndModal(wx.ID_OK)
