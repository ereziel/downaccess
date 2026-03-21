import re
import subprocess

import wx

_URL_RE = re.compile(r'https?://[^\s"\'<>]+', re.IGNORECASE)

from app.core import settings as cfg
from app.core import speech
from app.core import updater
from app.core import app_updater
from app.version import __version__
from app.core.downloader import DownloadInfo, DownloadProgress
from app.core.queue_manager import QueueManager
from app.ui.add_url_dialog import AddUrlDialog, FORMAT_MANUAL
from app.ui.download_list import DownloadList
from app.ui.format_dialog import FormatDialog
from app.ui.playlist_dialog import PlaylistDialog
from app.ui.search_dialog import SearchDialog, SearchResultsDialog
from app.ui.settings_dialog import SettingsDialog
from app.ui.uge_dialog import UGEDialog
from app.ui.update_dialog import UpdateDialog
from app.ui.contact_dialog import ContactDialog
from app.ui.error_dialog import ErrorDialog
from app.ui.report_dialog import ReportDialog
from app.core import error_reporter
from app.core.downloader import Downloader

APP_NAME = "DownAccess"

# IDs personnalisés pour les actions sans équivalent wx standard
ID_START        = wx.NewIdRef()
ID_PAUSE        = wx.NewIdRef()
ID_CANCEL       = wx.NewIdRef()
ID_RETRY        = wx.NewIdRef()
ID_MOVE_UP      = wx.NewIdRef()
ID_MOVE_DOWN    = wx.NewIdRef()
ID_UGE          = wx.NewIdRef()
ID_SHORTCUTS    = wx.NewIdRef()
ID_UPDATE_YDL   = wx.NewIdRef()
ID_CLIP_TOGGLE  = wx.NewIdRef()
ID_SEARCH       = wx.NewIdRef()
ID_UPDATE_APP   = wx.NewIdRef()
ID_CONTACT      = wx.NewIdRef()


class MainWindow(wx.Frame):
    def __init__(self, parent):
        super().__init__(
            parent,
            title=APP_NAME,
            style=wx.DEFAULT_FRAME_STYLE,
        )
        self.settings = cfg.load()
        self._build_ui()
        self._bind_events()
        self._init_queue()
        self._init_clipboard()
        self.Maximize()

    # ------------------------------------------------------------------
    # Queue
    # ------------------------------------------------------------------

    def _init_clipboard(self) -> None:
        self._clip_last: str = ""         # dernier contenu détecté
        self._clip_seen: set[str] = set() # URLs déjà ajoutées via surveillance
        self._clip_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_clip_tick, self._clip_timer)
        # Restaurer l'état de surveillance depuis les préférences
        if self.settings.get("clipboard_monitor", False):
            self.mi_clip_toggle.Check(True)
            self._clip_timer.Start(1500)  # vérif toutes les 1,5 s

    def _init_queue(self) -> None:
        # Stocke les données par download_id pour le retry
        self._dl_data: dict[str, dict] = {}
        # Dernier jalon annoncé par download_id (25/50/75)
        self._progress_milestones: dict[str, int] = {}
        # Mise à jour yt-dlp en cours au démarrage → bloquer les téléchargements
        self._updater_running: bool = True
        self._pending_downloads: list[tuple[str, str, str | None]] = []
        self._queue = QueueManager(
            settings=self.settings,
            on_info=self._on_dl_info,
            on_progress=self._on_dl_progress,
            on_complete=self._on_dl_complete,
            on_error=self._on_dl_error,
            on_playlist=self._on_dl_playlist,
        )

    def _on_dl_info(self, info: DownloadInfo) -> None:
        self.download_list.update_info(info.download_id, info.title, info.site, info.fmt)
        if info.download_id in self._dl_data:
            self._dl_data[info.download_id]["site"] = info.site
        title = info.title or info.url
        speech.speak(f"Téléchargement démarré : {title}.", interrupt=False)

    def _on_dl_progress(self, prog: DownloadProgress) -> None:
        self.download_list.update_progress(prog.download_id, prog.percent, prog.size)
        self.set_status(f"Téléchargement en cours… {prog.percent:.0f} %")
        # Annoncer les jalons 25 / 50 / 75 % (pas à chaque tick)
        last = self._progress_milestones.get(prog.download_id, 0)
        for milestone in (25, 50, 75):
            if prog.percent >= milestone > last:
                speech.speak(f"{milestone} pourcent.", interrupt=False)
                self._progress_milestones[prog.download_id] = milestone
                break

    def _on_dl_complete(self, download_id: str) -> None:
        self.download_list.complete_item(download_id)
        self._progress_milestones.pop(download_id, None)
        self.set_status("Téléchargement terminé.")
        speech.speak("Téléchargement terminé.")
        # Ouvrir le dossier si tous les téléchargements sont terminés
        if self.settings.get("open_folder_when_done") and self._all_done():
            self._open_download_folder()

    def _on_dl_error(self, download_id: str, message: str) -> None:
        self.download_list.error_item(download_id)
        self.set_status("Erreur lors du téléchargement.")
        speech.speak("Erreur lors du téléchargement.")
        dlg = ErrorDialog(self, message)
        dlg.ShowModal()
        if dlg.wants_report():
            self._start_error_report(download_id, message)
        dlg.Destroy()

    def _start_error_report(self, download_id: str, error_message: str) -> None:
        dl_data = self._dl_data.get(download_id, {})
        url         = dl_data.get("url", "")
        site        = dl_data.get("site", "")
        format_spec = dl_data.get("format_spec", "auto")
        format_id   = dl_data.get("format_id")
        referer     = dl_data.get("referer")
        cookies     = dl_data.get("cookies")

        report_dlg = ReportDialog(self, url=url, site=site, error_message=error_message)
        if report_dlg.ShowModal() != wx.ID_OK:
            report_dlg.Destroy()
            return

        comment = report_dlg.get_comment()
        report_dlg.set_running()

        verbose_log_holder = []

        import threading
        import threading as _th
        stop_evt  = _th.Event()
        pause_evt = _th.Event()

        def _run_verbose():
            log = []
            try:
                downloader = Downloader(self.settings)
                downloader.download(
                    download_id="diagnostic",
                    url=url,
                    on_progress=lambda _p: None,
                    stop_event=stop_evt,
                    pause_event=pause_evt,
                    format_spec=format_spec,
                    format_id=format_id,
                    referer=referer,
                    cookies=cookies,
                    verbose=True,
                    on_verbose_log=lambda txt: log.append(txt),
                )
            except Exception:
                pass
            verbose_log_holder.append(log[0] if log else "")
            wx.CallAfter(_send_report)

        def _send_report():
            report = error_reporter.build_report(
                url=url,
                site=site,
                format_spec=format_spec,
                error_message=error_message,
                verbose_log=verbose_log_holder[0] if verbose_log_holder else "",
                user_comment=comment,
            )
            error_reporter.send_report(
                report,
                on_done=lambda ok, msg: wx.CallAfter(_on_sent, ok, msg),
            )

        def _on_sent(success: bool, msg: str):
            report_dlg.set_done(success, msg)
            if success:
                self.set_status("Rapport d'erreur envoyé.")
            else:
                self.set_status("Échec de l'envoi du rapport.")

        threading.Thread(target=_run_verbose, daemon=True).start()

    def _on_dl_playlist(self, info: DownloadInfo) -> None:
        """Playlist détectée — supprimer l'item placeholder et montrer le dialogue."""
        self.download_list.remove_item(info.download_id)
        self._dl_data.pop(info.download_id, None)
        self.set_count(self.download_list.count())

        speech.speak(f"Playlist détectée : {info.title}. {len(info.playlist_entries)} vidéos.")

        with PlaylistDialog(self, info.title, info.playlist_entries) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                self.set_status("Téléchargement de playlist annulé.")
                return
            selected = dlg.get_selected_entries()

        fmt_choice = self._dl_data.get("__last_fmt__", "auto")
        for entry in selected:
            url = entry.get("url") or entry.get("webpage_url") or entry.get("id")
            if url:
                self._enqueue_url(url, fmt_choice)

        speech.speak(f"{len(selected)} vidéos ajoutées à la file.")

    def _all_done(self) -> bool:
        """Retourne True si aucun téléchargement n'est en cours ou en attente."""
        count = self.download_list.count()
        done  = self.download_list.count_by_status("Terminé")
        return count > 0 and done >= count

    def _open_download_folder(self) -> None:
        folder = self.settings.get("download_folder", "")
        if folder:
            subprocess.Popen(["explorer", folder])

    # ------------------------------------------------------------------
    # Construction de l'interface
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self._build_menubar()
        self._build_toolbar()
        self._build_main_panel()
        self._build_statusbar()

    def _build_menubar(self) -> None:
        mb = wx.MenuBar()

        # ---- Fichier ----
        file_menu = wx.Menu()
        self.mi_add = file_menu.Append(
            wx.ID_NEW, "&Ajouter URL...\tCtrl+N",
            "Ajouter un ou plusieurs URLs à télécharger",
        )
        self.mi_uge = file_menu.Append(
            ID_UGE, "Extraction &guidée...\tCtrl+G",
            "Ouvrir le navigateur intégré pour détecter les médias sur n'importe quelle page",
        )
        self.mi_search = file_menu.Append(
            ID_SEARCH, "&Rechercher...\tCtrl+F",
            "Rechercher des vidéos ou musiques sur YouTube, SoundCloud, etc.",
        )
        file_menu.AppendSeparator()
        self.mi_open_folder = file_menu.Append(
            wx.ID_OPEN, "&Ouvrir le dossier de destination\tCtrl+O",
            "Ouvrir le dossier de téléchargement dans l'Explorateur",
        )
        file_menu.AppendSeparator()
        self.mi_prefs = file_menu.Append(
            wx.ID_PREFERENCES, "&Préférences...\tCtrl+P",
            "Ouvrir les préférences",
        )
        file_menu.AppendSeparator()
        self.mi_quit = file_menu.Append(
            wx.ID_EXIT, "&Quitter\tAlt+F4",
            "Quitter DownAccess",
        )
        mb.Append(file_menu, "&Fichier")

        # ---- Téléchargements ----
        dl_menu = wx.Menu()
        self.mi_start = dl_menu.Append(
            ID_START, "Dé&marrer\tF5",
            "Démarrer les téléchargements en attente",
        )
        self.mi_pause = dl_menu.Append(
            ID_PAUSE, "&Pause / Reprendre\tSpace",
            "Mettre en pause ou reprendre le téléchargement sélectionné",
        )
        self.mi_cancel = dl_menu.Append(
            ID_CANCEL, "A&nnuler\tDelete",
            "Annuler et supprimer le téléchargement sélectionné",
        )
        dl_menu.AppendSeparator()
        self.mi_retry = dl_menu.Append(
            ID_RETRY, "&Réessayer\tF2",
            "Réessayer le téléchargement échoué sélectionné",
        )
        dl_menu.AppendSeparator()
        self.mi_move_up = dl_menu.Append(
            ID_MOVE_UP, "Mo&nter dans la file\tAlt+Up",
            "Déplacer l'item sélectionné vers le haut",
        )
        self.mi_move_down = dl_menu.Append(
            ID_MOVE_DOWN, "Descen&dre dans la file\tAlt+Down",
            "Déplacer l'item sélectionné vers le bas",
        )
        dl_menu.AppendSeparator()
        self.mi_clip_toggle = dl_menu.AppendCheckItem(
            ID_CLIP_TOGGLE, "Surveiller le &presse-papiers\tCtrl+Shift+V",
            "Détecter automatiquement les URLs copiées",
        )
        mb.Append(dl_menu, "&Téléchargements")

        # ---- Aide ----
        help_menu = wx.Menu()
        self.mi_shortcuts = help_menu.Append(
            ID_SHORTCUTS, "Raccourcis &clavier",
            "Afficher la liste des raccourcis clavier",
        )
        help_menu.AppendSeparator()
        self.mi_update_ydl = help_menu.Append(
            ID_UPDATE_YDL, "Mettre à jour &yt-dlp",
            "Télécharger et installer la dernière version de yt-dlp",
        )
        self.mi_update_app = help_menu.Append(
            ID_UPDATE_APP, "Mettre à jour &DownAccess",
            "Vérifier et installer la dernière version de DownAccess",
        )
        self.mi_contact = help_menu.Append(
            ID_CONTACT, "&Contacter le support / Faire une suggestion",
            "Envoyer un message, une suggestion ou signaler un problème",
        )
        help_menu.AppendSeparator()
        self.mi_about = help_menu.Append(
            wx.ID_ABOUT, "À &propos de DownAccess",
            "Informations sur DownAccess",
        )
        mb.Append(help_menu, "&Aide")

        self.SetMenuBar(mb)

    def _build_toolbar(self) -> None:
        tb = self.CreateToolBar(wx.TB_HORIZONTAL | wx.TB_TEXT | wx.TB_NOICONS)
        tb.AddTool(wx.ID_NEW,  "Ajouter URL", wx.NullBitmap, shortHelp="Ajouter URL (Ctrl+N)")
        tb.AddSeparator()
        tb.AddTool(ID_START,  "Démarrer",   wx.NullBitmap, shortHelp="Démarrer (F5)")
        tb.AddTool(ID_PAUSE,  "Pause",       wx.NullBitmap, shortHelp="Pause/Reprendre (Espace)")
        tb.AddTool(ID_CANCEL, "Annuler",     wx.NullBitmap, shortHelp="Annuler (Suppr)")
        tb.Realize()

    def _build_main_panel(self) -> None:
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.download_list = DownloadList(panel)
        sizer.Add(self.download_list, 1, wx.EXPAND | wx.ALL, 4)
        panel.SetSizer(sizer)

    def _build_statusbar(self) -> None:
        self.statusbar = self.CreateStatusBar(2)
        self.statusbar.SetStatusWidths([-1, 220])
        self.statusbar.SetStatusText("Prêt", 0)
        self.statusbar.SetStatusText("0 téléchargement(s)", 1)

    # ------------------------------------------------------------------
    # Liaison des événements
    # ------------------------------------------------------------------

    def _bind_events(self) -> None:
        self.Bind(wx.EVT_MENU, self._on_add_url,        id=wx.ID_NEW)
        self.Bind(wx.EVT_MENU, self._on_uge,            id=ID_UGE)
        self.Bind(wx.EVT_MENU, self._on_search,         id=ID_SEARCH)
        self.Bind(wx.EVT_MENU, self._on_open_folder,    id=wx.ID_OPEN)
        self.Bind(wx.EVT_MENU, self._on_preferences,    id=wx.ID_PREFERENCES)
        self.Bind(wx.EVT_MENU, self._on_quit,           id=wx.ID_EXIT)
        self.Bind(wx.EVT_MENU, self._on_start,          id=ID_START)
        self.Bind(wx.EVT_MENU, self._on_pause,          id=ID_PAUSE)
        self.Bind(wx.EVT_MENU, self._on_cancel,         id=ID_CANCEL)
        self.Bind(wx.EVT_MENU, self._on_retry,          id=ID_RETRY)
        self.Bind(wx.EVT_MENU, self._on_move_up,        id=ID_MOVE_UP)
        self.Bind(wx.EVT_MENU, self._on_move_down,      id=ID_MOVE_DOWN)
        self.Bind(wx.EVT_MENU, self._on_clip_toggle,    id=ID_CLIP_TOGGLE)
        self.Bind(wx.EVT_MENU, self._on_shortcuts,      id=ID_SHORTCUTS)
        self.Bind(wx.EVT_MENU, self._on_update_ytdlp,   id=ID_UPDATE_YDL)
        self.Bind(wx.EVT_MENU, self._on_update_app,     id=ID_UPDATE_APP)
        self.Bind(wx.EVT_MENU, self._on_contact,        id=ID_CONTACT)
        self.Bind(wx.EVT_MENU, self._on_about,          id=wx.ID_ABOUT)
        self.Bind(wx.EVT_CLOSE, self._on_close)
        # Ctrl+V global sur la fenêtre principale → coller URL directement
        accel = wx.AcceleratorTable([
            (wx.ACCEL_CTRL, ord("V"), wx.ID_PASTE),
            (wx.ACCEL_ALT, wx.WXK_UP,   ID_MOVE_UP),
            (wx.ACCEL_ALT, wx.WXK_DOWN, ID_MOVE_DOWN),
        ])
        self.SetAcceleratorTable(accel)
        self.Bind(wx.EVT_MENU, self._on_paste_url, id=wx.ID_PASTE)

    # ------------------------------------------------------------------
    # Gestionnaires d'événements
    # ------------------------------------------------------------------

    def _on_search(self, _event) -> None:
        with SearchDialog(self) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            query        = dlg.get_query()
            site_prefix  = dlg.get_site_prefix()
            site_label   = dlg.get_site_label()
            n            = dlg.get_n()

        search_url = f"{site_prefix}{n}:{query}"
        self.set_status(f"Recherche en cours : {query}…")
        speech.speak(f"Recherche sur {site_label}…")

        import threading
        from app.core.downloader import Downloader, DownloadError

        result = {}

        def fetch():
            try:
                import yt_dlp
                opts = {
                    "quiet": True,
                    "no_warnings": True,
                    "extract_flat": True,
                    "skip_download": True,
                }
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(search_url, download=False)
                entries = list(info.get("entries") or []) if info else []
                result["entries"] = [e for e in entries if e]
            except Exception as exc:
                result["error"] = str(exc)
            wx.CallAfter(self._on_search_done, site_label, result)

        threading.Thread(target=fetch, daemon=True).start()

    def _on_search_done(self, site_label: str, result: dict) -> None:
        if "error" in result:
            self.set_status("Erreur lors de la recherche.")
            speech.speak("Erreur lors de la recherche.")
            wx.MessageBox(
                f"Erreur de recherche :\n\n{result['error']}",
                "Erreur", wx.OK | wx.ICON_ERROR,
            )
            return

        entries = result.get("entries", [])
        if not entries:
            self.set_status("Aucun résultat trouvé.")
            speech.speak("Aucun résultat trouvé.")
            return

        with SearchResultsDialog(self, site_label, entries) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                self.set_status("Recherche annulée.")
                return
            selected = dlg.get_selected_entries()
            fmt      = dlg.get_format()

        for entry in selected:
            url = entry.get("url") or entry.get("webpage_url")
            if url:
                self._enqueue_url(url, format_spec=fmt)

        n = len(selected)
        msg = f"{n} résultat{'s' if n > 1 else ''} ajouté{'s' if n > 1 else ''} à la file."
        self.set_status(msg)
        speech.speak(msg)

    def _on_uge(self, _event) -> None:
        dlg = UGEDialog(
            self,
            on_add_url=lambda url, referer=None, cookies=None:
                self._enqueue_url(url, referer=referer, cookies=cookies),
        )
        dlg.Show()

    def _on_add_url(self, _event) -> None:
        with AddUrlDialog(self) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            urls       = dlg.get_urls()
            fmt_choice = dlg.get_format_choice()

        if fmt_choice == FORMAT_MANUAL and len(urls) == 1:
            self._enqueue_with_format_selection(urls[0])
        else:
            for url in urls:
                self._enqueue_url(url, fmt_choice)

    def _enqueue_url(self, url: str, format_spec: str = "auto",
                     format_id: str | None = None,
                     referer: str | None = None,
                     cookies: str | None = None) -> None:
        # Si la mise à jour yt-dlp est en cours, mettre en attente
        if self._updater_running:
            self._pending_downloads.append((url, format_spec, format_id))
            self.set_status("URL en file d'attente — mise à jour yt-dlp en cours…")
            speech.speak("URL ajoutée. Le téléchargement démarrera après la mise à jour de yt-dlp.", interrupt=False)
            return
        dl_id = self._queue.add(url, format_spec=format_spec, format_id=format_id,
                                referer=referer, cookies=cookies)
        label = format_spec.upper() if format_spec != "auto" else "Auto"
        self.download_list.add_item(dl_id, url, site="—", fmt=label)
        # Stocker pour retry et rapport d'erreur
        self._dl_data[dl_id] = {
            "url": url, "format_spec": format_spec, "format_id": format_id,
            "referer": referer, "cookies": cookies, "site": "",
        }
        self._dl_data["__last_fmt__"] = format_spec
        self.set_count(self.download_list.count())
        self.set_status(f"URL ajoutée : {url}")
        speech.speak(f"Ajouté à la file.", interrupt=False)

    def _enqueue_with_format_selection(self, url: str) -> None:
        """Fetch info → FormatDialog → enqueue avec format_id."""
        self.set_status("Récupération des formats disponibles…")
        speech.speak("Récupération des formats disponibles.")

        import threading
        from app.core.downloader import Downloader, DownloadError

        result = {}

        def fetch():
            try:
                dl = Downloader(self.settings)
                info = dl.fetch_info("__fmt__", url)
                result["info"] = info
            except DownloadError as exc:
                result["error"] = str(exc)
            wx.CallAfter(self._on_formats_ready, url, result)

        threading.Thread(target=fetch, daemon=True).start()

    def _on_formats_ready(self, url: str, result: dict) -> None:
        if "error" in result:
            self.set_status("Impossible de récupérer les formats.")
            speech.speak("Impossible de récupérer les formats.")
            wx.MessageBox(
                f"Impossible de récupérer les formats :\n\n{result['error']}",
                "Erreur", wx.OK | wx.ICON_ERROR,
            )
            return

        info = result.get("info")
        if not info:
            self.set_status("Aucune information disponible.")
            return

        formats = info.raw_formats if hasattr(info, "raw_formats") else []
        if not formats:
            # Pas de formats détaillés → enqueue en auto
            self._enqueue_url(url, "auto")
            self.set_status("Formats non disponibles, téléchargement en qualité auto.")
            return

        with FormatDialog(self, info.title, formats) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                fmt_id = dlg.get_format_id()
                self._enqueue_url(url, "manual", format_id=fmt_id)
            else:
                self.set_status("Sélection de format annulée.")

    def _on_open_folder(self, _event) -> None:
        self._open_download_folder()

    def _on_preferences(self, _event) -> None:
        with SettingsDialog(self, self.settings) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                self.settings = dlg.get_settings()
                cfg.save(self.settings)
                self._queue._settings = self.settings
                speech.speak("Préférences enregistrées.")

    def _on_quit(self, _event) -> None:
        self.Close()

    def _on_start(self, _event) -> None:
        # Sera connecté au QueueManager en Phase 2
        wx.MessageBox(
            "Démarrage de la file disponible en Phase 2.",
            APP_NAME, wx.OK | wx.ICON_INFORMATION,
        )

    def _on_pause(self, _event) -> None:
        dl_id = self.download_list.get_selected_id()
        if dl_id is None:
            speech.speak("Aucun téléchargement sélectionné.")
            return
        if self._queue.is_paused(dl_id):
            self._queue.resume(dl_id)
            self.download_list.set_status(dl_id, "En cours")
            speech.speak("Téléchargement repris.")
            self.set_status("Téléchargement repris.")
        else:
            self._queue.pause(dl_id)
            self.download_list.set_status(dl_id, "En pause")
            speech.speak("Téléchargement mis en pause.")
            self.set_status("Téléchargement mis en pause.")

    def _on_cancel(self, _event) -> None:
        dl_id = self.download_list.get_selected_id()
        if dl_id is None:
            self.set_status("Aucun téléchargement sélectionné.")
            return
        if wx.MessageBox(
            "Annuler et supprimer ce téléchargement ?",
            "Confirmer l'annulation",
            wx.YES_NO | wx.ICON_QUESTION,
        ) == wx.YES:
            self._queue.cancel(dl_id)
            self.download_list.remove_selected()
            self._progress_milestones.pop(dl_id, None)
            self.set_status("Téléchargement supprimé.")
            speech.speak("Téléchargement supprimé.")
            self.set_count(self.download_list.count())

    def _on_retry(self, _event) -> None:
        dl_id = self.download_list.get_selected_id()
        if dl_id is None:
            self.set_status("Aucun téléchargement sélectionné.")
            return
        data = self._dl_data.get(dl_id)
        if not data:
            self.set_status("Impossible de réessayer : données introuvables.")
            return
        # Supprimer l'item échoué et relancer
        self.download_list.remove_selected()
        self._dl_data.pop(dl_id, None)
        self._enqueue_url(data["url"], data["format_spec"], data.get("format_id"))
        self.set_status("Téléchargement relancé.")

    def _on_move_up(self, _event) -> None:
        dl_id = self.download_list.get_selected_id()
        if dl_id is None:
            return
        moved = self._queue.move_up(dl_id)
        if moved:
            self.download_list.move_item_up(dl_id)
            speech.speak("Déplacé vers le haut.", interrupt=False)
        else:
            speech.speak("Impossible de déplacer.", interrupt=False)

    def _on_move_down(self, _event) -> None:
        dl_id = self.download_list.get_selected_id()
        if dl_id is None:
            return
        moved = self._queue.move_down(dl_id)
        if moved:
            self.download_list.move_item_down(dl_id)
            speech.speak("Déplacé vers le bas.", interrupt=False)
        else:
            speech.speak("Impossible de déplacer.", interrupt=False)

    def _on_paste_url(self, _event) -> None:
        """Ctrl+V global : colle l'URL du presse-papiers sans ouvrir de dialogue."""
        urls = _urls_from_clipboard()
        if not urls:
            self.set_status("Aucune URL valide dans le presse-papiers.")
            speech.speak("Aucune URL dans le presse-papiers.")
            return
        for url in urls:
            self._enqueue_url(url)
        n = len(urls)
        msg = f"{n} URL{'s' if n > 1 else ''} ajoutée{'s' if n > 1 else ''} depuis le presse-papiers."
        self.set_status(msg)
        speech.speak(msg)

    def _on_clip_toggle(self, _event) -> None:
        """Active/désactive la surveillance du presse-papiers."""
        active = self.mi_clip_toggle.IsChecked()
        self.settings["clipboard_monitor"] = active
        cfg.save(self.settings)
        if active:
            self._clip_seen.clear()
            self._clip_last = _clipboard_text()
            self._clip_timer.Start(1500)
            speech.speak("Surveillance du presse-papiers activée.")
            self.set_status("Surveillance du presse-papiers activée.")
        else:
            self._clip_timer.Stop()
            speech.speak("Surveillance du presse-papiers désactivée.")
            self.set_status("Surveillance du presse-papiers désactivée.")

    def _on_clip_tick(self, _event) -> None:
        """Appelé toutes les 1,5 s — vérifie si une nouvelle URL a été copiée."""
        text = _clipboard_text()
        if text == self._clip_last:
            return
        self._clip_last = text
        urls = _URL_RE.findall(text)
        new_urls = [u for u in urls if u not in self._clip_seen]
        for url in new_urls:
            self._clip_seen.add(url)
            self._enqueue_url(url)
            msg = f"URL détectée et ajoutée : {url}"
            self.set_status(msg)
            speech.speak(msg)

    def _on_shortcuts(self, _event) -> None:
        msg = (
            "Raccourcis clavier — DownAccess\n\n"
            "Ctrl+N           Ajouter URL(s)\n"
            "Ctrl+F           Rechercher (YouTube, SoundCloud…)\n"
            "Ctrl+G           Extraction guidée (navigateur intégré)\n"
            "Ctrl+V           Coller URL depuis le presse-papiers\n"
            "Ctrl+Shift+V     Activer/désactiver la surveillance du presse-papiers\n"
            "F5               Démarrer la file\n"
            "Espace           Pause / Reprendre\n"
            "Suppr            Annuler / Supprimer\n"
            "F2               Réessayer\n"
            "Alt+Haut         Monter dans la file\n"
            "Alt+Bas          Descendre dans la file\n"
            "Ctrl+O           Ouvrir le dossier de destination\n"
            "Ctrl+P           Préférences\n"
            "Alt+F4           Quitter\n"
        )
        wx.MessageBox(msg, "Raccourcis clavier", wx.OK | wx.ICON_INFORMATION)

    def _on_update_app(self, _event) -> None:
        self.mi_update_app.Enable(False)
        self.set_status("Vérification de la mise à jour DownAccess…")
        speech.speak("Vérification de la mise à jour.")
        app_updater.check_for_update(
            on_done=lambda status, info, notes: wx.CallAfter(self._on_app_update_checked, status, info, notes)
        )

    def _on_app_update_checked(self, status: str, info: str, release_notes: str = "") -> None:
        self.mi_update_app.Enable(True)
        if status == "up_to_date":
            msg = f"DownAccess est à jour. Version {info}."
            self.set_status(msg)
            speech.speak(msg)
        elif status == "update_available":
            dlg = UpdateDialog(self, new_version=info, release_notes=release_notes)
            if dlg.ShowModal() == wx.ID_OK:
                self.set_status(f"Téléchargement de DownAccess {info}…")
                self.mi_update_app.Enable(False)
                app_updater.download_and_install(
                    new_version=info,
                    on_progress=lambda pct: wx.CallAfter(self._on_app_dl_progress, pct),
                    on_error=lambda msg: wx.CallAfter(self._on_app_dl_error, msg),
                )
            else:
                self.set_status(f"Mise à jour DownAccess {info} reportée.")
            dlg.Destroy()
        elif status == "error":
            msg = "Impossible de vérifier la mise à jour."
            self.set_status(msg)
            speech.speak(msg)

    def _on_app_dl_progress(self, percent: float) -> None:
        self.set_status(f"Téléchargement de la mise à jour… {percent:.0f} %")
        for milestone in (25, 50, 75, 100):
            if abs(percent - milestone) < 2:
                speech.speak(f"{milestone} pourcent.", interrupt=False)
                break

    def _on_app_dl_error(self, message: str) -> None:
        self.mi_update_app.Enable(True)
        self.set_status("Erreur lors du téléchargement de la mise à jour.")
        speech.speak("Erreur lors du téléchargement.")
        wx.MessageBox(
            f"Impossible de télécharger la mise à jour :\n\n{message}",
            "Erreur de mise à jour", wx.OK | wx.ICON_ERROR,
        )

    def check_app_update_at_startup(self) -> None:
        """Vérification silencieuse au démarrage — annonce seulement si mise à jour dispo."""
        def _on_done(status, info, notes):
            if status == "update_available":
                wx.CallAfter(self._on_app_update_checked, status, info, notes)
        app_updater.check_for_update(on_done=_on_done)

    def _on_update_ytdlp(self, _event) -> None:
        self.set_status("Vérification de la version yt-dlp…")
        speech.speak("Vérification de la version yt-dlp.")
        self.mi_update_ydl.Enable(False)

        updater.check_and_update(
            on_done=lambda status, info: wx.CallAfter(self.on_ytdlp_update_done, status, info)
        )

    def _on_contact(self, _event) -> None:
        dlg = ContactDialog(self)
        if dlg.ShowModal() != wx.ID_OK:
            dlg.Destroy()
            return

        contact_type = dlg.get_type_key()
        email        = dlg.get_email()
        message      = dlg.get_message()

        dlg.set_sending()

        def _on_done(success: bool, msg: str) -> None:
            wx.CallAfter(dlg.set_done, success, msg)
            if success:
                wx.CallAfter(self.set_status, "Message envoyé.")
            else:
                wx.CallAfter(self.set_status, "Échec de l'envoi du message.")

        error_reporter.send_contact(
            contact_type=contact_type,
            email=email,
            message=message,
            on_done=_on_done,
        )

    def _on_about(self, _event) -> None:
        wx.MessageBox(
            "DownAccess\n\n"
            "Téléchargeur vidéo/audio Windows,\n"
            "100 % accessible NVDA.\n\n"
            "Propulsé par yt-dlp et ffmpeg.",
            "À propos de DownAccess",
            wx.OK | wx.ICON_INFORMATION,
        )

    def _on_close(self, event) -> None:
        cfg.save(self.settings)
        event.Skip()

    # ------------------------------------------------------------------
    # API publique (appelée depuis les threads via wx.CallAfter)
    # ------------------------------------------------------------------

    def on_ytdlp_update_done(self, status: str, info: str) -> None:
        """
        Callback commun pour bootstrap() et le menu Mettre à jour.
        status : "up_to_date" | "updated" | "installed" | "error"
        info   : version ou message d'erreur
        """
        self.mi_update_ydl.Enable(True)
        self._updater_running = False

        if status == "up_to_date":
            msg = f"yt-dlp est à jour. Version {info}."
            self.set_status(msg)
            speech.speak(msg)
        elif status == "updated":
            msg = f"yt-dlp mis à jour. Nouvelle version : {info}."
            self.set_status(msg)
            speech.speak(msg)
        elif status == "installed":
            msg = f"yt-dlp installé. Version {info}."
            self.set_status(msg)
            speech.speak(msg)
        elif status == "error":
            msg = "Échec de la mise à jour de yt-dlp."
            self.set_status(msg)
            speech.speak(msg)
            wx.MessageBox(
                f"La mise à jour de yt-dlp a échoué :\n\n{info}\n\n"
                "Vérifiez votre connexion et réessayez via Aide → Mettre à jour yt-dlp.",
                "Erreur yt-dlp",
                wx.OK | wx.ICON_ERROR,
            )

        # Démarrer les téléchargements mis en attente pendant la mise à jour
        if self._pending_downloads:
            pending = self._pending_downloads[:]
            self._pending_downloads.clear()
            n = len(pending)
            speech.speak(
                f"Démarrage de {n} téléchargement{'s' if n > 1 else ''} en attente.",
                interrupt=False,
            )
            for url, fmt, fid in pending:
                self._enqueue_url(url, fmt, fid)

    def set_status(self, message: str) -> None:
        """Met à jour le premier panneau de la barre de statut (lu par NVDA)."""
        self.statusbar.SetStatusText(message, 0)

    def set_count(self, count: int) -> None:
        """Met à jour le compteur de téléchargements dans la barre de statut."""
        self.statusbar.SetStatusText(f"{count} téléchargement(s)", 1)


# ------------------------------------------------------------------
# Fonctions utilitaires presse-papiers (hors classe)
# ------------------------------------------------------------------

def _clipboard_text() -> str:
    """Retourne le texte brut du presse-papiers, ou chaîne vide."""
    try:
        if wx.TheClipboard.Open():
            data = wx.TextDataObject()
            ok = wx.TheClipboard.GetData(data)
            wx.TheClipboard.Close()
            return data.GetText() if ok else ""
    except Exception:
        pass
    return ""


def _urls_from_clipboard() -> list[str]:
    """Extrait les URLs http/https du presse-papiers."""
    text = _clipboard_text()
    return [u for u in _URL_RE.findall(text) if u]

