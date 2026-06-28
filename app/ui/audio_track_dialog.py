import wx

from app.core import speech
from app.core.custom_sites import AudioTrack


class AudioTrackDialog(wx.Dialog):
    """
    Sélecteur de pistes audio (français, audiodescription, version originale…).

    Affiché quand un site personnalisé (france.tv, arte.tv) propose plusieurs
    pistes audio.

    - Mode **vidéo** (`single_select=False`) : l'utilisateur peut cocher une OU
      plusieurs pistes ; toutes sont réunies dans un seul fichier (commutables
      dans le lecteur). wx.ListCtrl + EnableCheckBoxes() → cases natives UIA/MSAA.
    - Mode **audio** (`single_select=True`, mp3/m4a) : choix UNIQUE via wx.RadioBox
      (un fichier audio ne porte qu'une piste ; extraire deux pistes en
      téléchargerait deux pour n'en garder qu'une). Boutons radio = annoncés
      « bouton radio, X sur Y » par NVDA.
    """

    def __init__(self, parent, title: str, tracks: list[AudioTrack],
                 single_select: bool = False):
        super().__init__(
            parent,
            title=_("Choisir la piste audio — {title}").format(title=title)
            if single_select
            else _("Choisir les pistes audio — {title}").format(title=title),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self._tracks = tracks
        self._single = single_select
        self._selected: list[AudioTrack] = []
        self._build_ui()
        self._bind_events()
        self.SetMinSize((460, 320))
        self.Fit()
        self.CentreOnParent()
        if single_select:
            speech.speak(
                _("Choix de la piste audio pour {title}. {count} pistes "
                  "disponibles. Choisissez celle à télécharger.").format(
                      title=title, count=len(tracks))
            )
        else:
            speech.speak(
                _("Choix des pistes audio pour {title}. {count} pistes "
                  "disponibles. Cochez celles à télécharger.").format(
                      title=title, count=len(tracks))
            )

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        if self._single:
            lbl = wx.StaticText(
                panel,
                label=_("Cette vidéo propose plusieurs pistes audio. Choisissez "
                        "celle à extraire :"),
            )
            # Choix unique : boutons radio (un fichier audio = une seule piste).
            self.radio = wx.RadioBox(
                panel,
                label=_("Piste audio"),
                choices=[t.label for t in self._tracks],
                majorDimension=1,
                style=wx.RA_SPECIFY_COLS,
            )
            self.radio.SetSelection(0)
            content = self.radio
        else:
            lbl = wx.StaticText(
                panel,
                label=_("Cette vidéo propose plusieurs pistes audio. Cochez "
                        "celles à télécharger (une ou plusieurs) :"),
            )
            # Choix multiple : cases à cocher natives (UIA/MSAA → NVDA).
            self.lst = wx.ListCtrl(
                panel,
                style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.BORDER_SUNKEN,
                name=_("Pistes audio"),
            )
            self.lst.EnableCheckBoxes()
            self.lst.InsertColumn(0, _("Piste audio"), width=420)
            for i, track in enumerate(self._tracks):
                self.lst.InsertItem(i, track.label)
            self.lst.CheckItem(0, True)   # pré-cocher la première piste
            content = self.lst

        btn_sizer = wx.StdDialogButtonSizer()
        ok_label = (_("Télécharger la piste choisie") if self._single
                    else _("Télécharger les pistes cochées"))
        self.btn_ok     = wx.Button(panel, wx.ID_OK,     label=ok_label)
        self.btn_cancel = wx.Button(panel, wx.ID_CANCEL, label=_("Annuler"))
        self.btn_ok.SetDefault()
        btn_sizer.AddButton(self.btn_ok)
        btn_sizer.AddButton(self.btn_cancel)
        btn_sizer.Realize()

        main_sizer.Add(lbl,       0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 12)
        main_sizer.Add(content,   1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 6)
        main_sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 12)

        panel.SetSizer(main_sizer)

        self.btn_ok.MoveAfterInTabOrder(content)
        self.btn_cancel.MoveAfterInTabOrder(self.btn_ok)
        content.SetFocus()

    def _bind_events(self) -> None:
        self.btn_ok.Bind(wx.EVT_BUTTON, self._on_ok)

    # ------------------------------------------------------------------
    # Événements
    # ------------------------------------------------------------------

    def _on_ok(self, _event) -> None:
        if self._single:
            self._selected = [self._tracks[self.radio.GetSelection()]]
            self.EndModal(wx.ID_OK)
            return

        chosen = [
            self._tracks[i]
            for i in range(self.lst.GetItemCount())
            if self.lst.IsItemChecked(i)
        ]
        if not chosen:
            speech.speak(_("Veuillez cocher au moins une piste."))
            wx.MessageBox(
                _("Veuillez cocher au moins une piste audio."),
                _("Aucune piste cochée"),
                wx.OK | wx.ICON_WARNING,
                self,
            )
            self.lst.SetFocus()
            return
        self._selected = chosen
        self.EndModal(wx.ID_OK)

    # ------------------------------------------------------------------
    # API publique
    # ------------------------------------------------------------------

    def get_selected_tracks(self) -> list[AudioTrack]:
        return self._selected
