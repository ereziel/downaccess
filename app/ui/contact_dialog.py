"""
Dialogue de contact / suggestion pour DownAccess.
Permet à l'utilisateur d'envoyer un message, une suggestion ou un retour.
"""
import wx
from app.core import speech
from app.core import error_reporter


CONTACT_TYPES = [
    ("suggestion", "Suggestion de fonctionnalité"),
    ("bug",        "Signaler un bug"),
    ("question",   "Question générale"),
    ("other",      "Autre"),
]


class ContactDialog(wx.Dialog):

    def __init__(self, parent, saved_email: str = "", on_email_saved=None):
        super().__init__(
            parent,
            title="Contacter le support — DownAccess",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
            size=(560, 460),
        )
        self._saved_email    = saved_email
        self._on_email_saved = on_email_saved  # Callable[[str], None] | None
        self._build_ui()
        self.txt_email.SetFocus()
        self.Centre()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Email
        lbl_email = wx.StaticText(self, label="Votre adresse email (obligatoire pour recevoir une réponse) :")
        sizer.Add(lbl_email, 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)
        self.txt_email = wx.TextCtrl(self, name="Adresse email", value=self._saved_email)
        sizer.Add(self.txt_email, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 8)

        # Type de message
        lbl_type = wx.StaticText(self, label="Type de message :")
        sizer.Add(lbl_type, 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)
        self.cho_type = wx.Choice(
            self,
            choices=[label for _, label in CONTACT_TYPES],
            name="Type de message",
        )
        self.cho_type.SetSelection(0)
        sizer.Add(self.cho_type, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 8)

        # Message
        lbl_msg = wx.StaticText(self, label="Message :")
        sizer.Add(lbl_msg, 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)
        self.txt_message = wx.TextCtrl(
            self,
            style=wx.TE_MULTILINE,
            name="Message",
        )
        sizer.Add(self.txt_message, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 8)

        # Statut (caché au départ)
        self.lbl_status = wx.StaticText(self, label="")
        sizer.Add(self.lbl_status, 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)

        # Boutons
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_send   = wx.Button(self, wx.ID_OK,     label="Envoyer",
                                    name="Envoyer le message")
        self.btn_cancel = wx.Button(self, wx.ID_CANCEL, label="Annuler",
                                    name="Annuler")
        btn_sizer.AddStretchSpacer()
        btn_sizer.Add(self.btn_send,   0, wx.RIGHT, 8)
        btn_sizer.Add(self.btn_cancel, 0, wx.RIGHT, 8)
        sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 10)

        self.btn_send.Bind(wx.EVT_BUTTON,   self._on_send)
        self.btn_cancel.Bind(wx.EVT_BUTTON, lambda _e: self.EndModal(wx.ID_CANCEL))

        self.SetSizer(sizer)

    # ------------------------------------------------------------------
    # Transitions d'état
    # ------------------------------------------------------------------

    def set_sending(self) -> None:
        self.btn_send.Enable(False)
        self.btn_cancel.Enable(False)
        self.lbl_status.SetLabel("Envoi en cours…")
        speech.speak("Envoi en cours.")
        self.Layout()

    def set_done(self, success: bool, message: str) -> None:
        self.lbl_status.SetLabel(message)
        self.btn_cancel.SetLabel("Fermer")
        self.btn_cancel.Enable(True)
        self.btn_cancel.SetFocus()
        if success:
            self.btn_send.Enable(False)
        else:
            self.btn_send.Enable(True)
        speech.speak(message)
        self.Layout()

    # ------------------------------------------------------------------
    # Accesseurs
    # ------------------------------------------------------------------

    def get_type_key(self) -> str:
        idx = self.cho_type.GetSelection()
        if 0 <= idx < len(CONTACT_TYPES):
            return CONTACT_TYPES[idx][0]
        return "other"

    def get_type_label(self) -> str:
        idx = self.cho_type.GetSelection()
        if 0 <= idx < len(CONTACT_TYPES):
            return CONTACT_TYPES[idx][1]
        return "Autre"

    def get_email(self) -> str:
        return self.txt_email.GetValue().strip()

    def get_message(self) -> str:
        return self.txt_message.GetValue().strip()

    # ------------------------------------------------------------------
    # Validation + envoi
    # ------------------------------------------------------------------

    def _on_send(self, _event) -> None:
        email   = self.get_email()
        message = self.get_message()

        if not email:
            wx.MessageBox("Veuillez entrer votre adresse email.", "Champ manquant",
                          wx.OK | wx.ICON_WARNING)
            self.txt_email.SetFocus()
            return

        import re
        if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
            wx.MessageBox("L'adresse email semble invalide.", "Email invalide",
                          wx.OK | wx.ICON_WARNING)
            self.txt_email.SetFocus()
            return

        if not message:
            wx.MessageBox("Veuillez écrire un message.", "Champ manquant",
                          wx.OK | wx.ICON_WARNING)
            self.txt_message.SetFocus()
            return

        # Sauvegarder l'email pour la prochaine fois
        if self._on_email_saved:
            self._on_email_saved(email)

        # Le dialog reste ouvert pendant l'envoi
        self.set_sending()
        error_reporter.send_contact(
            contact_type=self.get_type_key(),
            email=email,
            message=message,
            on_done=lambda ok, msg: wx.CallAfter(self.set_done, ok, msg),
        )
