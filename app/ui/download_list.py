import wx

# (label, width_px)
COLUMNS = [
    ("Titre",       300),
    ("Site",        120),
    ("Format",       90),
    ("Statut",      110),
    ("Progression", 100),
    ("Taille",       80),
]

COL_TITLE = 0
COL_SITE  = 1
COL_FMT   = 2
COL_STATE = 3
COL_PCT   = 4
COL_SIZE  = 5


class DownloadList(wx.ListCtrl):
    """
    File de téléchargement affichée sous forme de tableau.
    Utilise wx.ListCtrl (Report) pour un support NVDA/MSAA natif optimal.
    """

    def __init__(self, parent):
        super().__init__(
            parent,
            style=wx.LC_REPORT | wx.LC_HRULES | wx.LC_VRULES | wx.BORDER_SUNKEN,
        )
        self.SetName("File de téléchargement")
        self._setup_columns()
        # download_id (str) -> row index (int)
        self._items: dict[str, int] = {}

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _setup_columns(self) -> None:
        for i, (label, width) in enumerate(COLUMNS):
            self.InsertColumn(i, label, width=width)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_item(self, download_id: str, title: str, site: str, fmt: str = "") -> int:
        """Ajoute un item dans la liste. Retourne l'index de la ligne."""
        idx = self.GetItemCount()
        self.InsertItem(idx, title)
        self.SetItem(idx, COL_SITE,  site)
        self.SetItem(idx, COL_FMT,   fmt)
        self.SetItem(idx, COL_STATE, "En attente")
        self.SetItem(idx, COL_PCT,   "0 %")
        self.SetItem(idx, COL_SIZE,  "")
        self._items[download_id] = idx
        # Sélectionner le nouvel item → NVDA l'annonce
        self.Select(idx)
        self.Focus(idx)
        return idx

    def update_info(self, download_id: str, title: str, site: str, fmt: str = "") -> None:
        """Met à jour titre, site et format une fois les métadonnées récupérées."""
        idx = self._items.get(download_id)
        if idx is None:
            return
        self.SetItem(idx, COL_TITLE, title)
        self.SetItem(idx, COL_SITE,  site)
        if fmt:
            self.SetItem(idx, COL_FMT, fmt)

    def update_progress(self, download_id: str, percent: float, size: str = "") -> None:
        """Met à jour la progression d'un téléchargement en cours."""
        idx = self._items.get(download_id)
        if idx is None:
            return
        self.SetItem(idx, COL_STATE, "En cours")
        self.SetItem(idx, COL_PCT,   f"{percent:.0f} %")
        if size:
            self.SetItem(idx, COL_SIZE, size)

    def set_status(self, download_id: str, status: str) -> None:
        idx = self._items.get(download_id)
        if idx is None:
            return
        self.SetItem(idx, COL_STATE, status)

    def complete_item(self, download_id: str, size: str = "") -> None:
        idx = self._items.get(download_id)
        if idx is None:
            return
        self.SetItem(idx, COL_STATE, "Terminé")
        self.SetItem(idx, COL_PCT,   "100 %")
        if size:
            self.SetItem(idx, COL_SIZE, size)

    def error_item(self, download_id: str) -> None:
        idx = self._items.get(download_id)
        if idx is None:
            return
        self.SetItem(idx, COL_STATE, "Erreur")

    def remove_item(self, download_id: str) -> None:
        """Supprime un item par son download_id."""
        idx = self._items.get(download_id)
        if idx is None:
            return
        self.DeleteItem(idx)
        del self._items[download_id]
        self._items = {k: (v - 1 if v > idx else v) for k, v in self._items.items()}

    def count_by_status(self, status: str) -> int:
        """Compte les items ayant un statut donné."""
        n = 0
        for idx in self._items.values():
            if self.GetItemText(idx, COL_STATE) == status:
                n += 1
        return n

    def remove_selected(self) -> str | None:
        """Supprime l'item sélectionné. Retourne son download_id ou None."""
        idx = self.GetFirstSelected()
        if idx == -1:
            return None
        dl_id = next((k for k, v in self._items.items() if v == idx), None)
        self.DeleteItem(idx)
        if dl_id:
            del self._items[dl_id]
        # Réindexer les items dont le rang était supérieur à idx
        self._items = {
            k: (v - 1 if v > idx else v)
            for k, v in self._items.items()
        }
        return dl_id

    def get_selected_id(self) -> str | None:
        idx = self.GetFirstSelected()
        if idx == -1:
            return None
        return next((k for k, v in self._items.items() if v == idx), None)

    def move_item_up(self, download_id: str) -> bool:
        idx = self._items.get(download_id)
        if idx is None or idx == 0:
            return False
        self._swap_rows(idx, idx - 1)
        for k in self._items:
            if self._items[k] == idx - 1 and k != download_id:
                self._items[k] = idx
                break
        self._items[download_id] = idx - 1
        self.Select(idx - 1)
        self.Focus(idx - 1)
        return True

    def move_item_down(self, download_id: str) -> bool:
        idx = self._items.get(download_id)
        if idx is None or idx >= self.GetItemCount() - 1:
            return False
        self._swap_rows(idx, idx + 1)
        for k in self._items:
            if self._items[k] == idx + 1 and k != download_id:
                self._items[k] = idx
                break
        self._items[download_id] = idx + 1
        self.Select(idx + 1)
        self.Focus(idx + 1)
        return True

    def _swap_rows(self, row_a: int, row_b: int) -> None:
        data_a = [self.GetItemText(row_a, col) for col in range(len(COLUMNS))]
        data_b = [self.GetItemText(row_b, col) for col in range(len(COLUMNS))]
        for col, val in enumerate(data_b):
            self.SetItem(row_a, col, val)
        for col, val in enumerate(data_a):
            self.SetItem(row_b, col, val)

    def count(self) -> int:
        return self.GetItemCount()
