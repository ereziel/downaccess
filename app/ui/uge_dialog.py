"""
Extraction Guidée (User Guided Extraction)

L'utilisateur navigue dans un vrai navigateur Chrome (via DrissionPage).
Un script JS intercepte toutes les requêtes XHR/fetch et les éléments
<video>/<source> pour détecter les URLs de médias en temps réel.
La fenêtre DownAccess affiche la liste des médias détectés.
"""
import json
import logging
import threading
import urllib.request

import wx

from app.core import speech
from app.core.browser import find_browser, browser_name

_log = logging.getLogger("downaccess.uge")

# ------------------------------------------------------------------
# Script JS injecté après chaque chargement de page
# ------------------------------------------------------------------

_MONITOR_SCRIPT = r"""
(function() {
    if (window.__da_initialized) return;
    window.__da_initialized = true;
    window.__da_urls = window.__da_urls || [];

    var MEDIA_RE = /\.(mp4|m4v|webm|mkv|flv|mov|m3u8|mpd|ts|mp3|aac|ogg|wav|opus)(\?|#|$)/i;

    function addUrl(url) {
        if (!url || typeof url !== 'string') return;
        if (url.startsWith('blob:') || url.startsWith('data:')) return;
        if (!MEDIA_RE.test(url)) return;
        if (window.__da_urls.indexOf(url) !== -1) return;
        window.__da_urls.push(url);
    }

    // Intercepter XMLHttpRequest
    var origOpen = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function(method, url) {
        addUrl(String(url));
        return origOpen.apply(this, arguments);
    };

    // Intercepter fetch
    var origFetch = window.fetch;
    if (origFetch) {
        window.fetch = function(input, init) {
            if (typeof input === 'string') addUrl(input);
            else if (input && typeof input.url === 'string') addUrl(input.url);
            return origFetch.apply(this, arguments);
        };
    }

    // Observer les éléments video/source/audio ajoutés au DOM
    function scanNode(node) {
        if (!node || !node.tagName) return;
        var tag = node.tagName.toUpperCase();
        if (tag === 'VIDEO' || tag === 'SOURCE' || tag === 'AUDIO') {
            if (node.src) addUrl(node.src);
            if (node.currentSrc) addUrl(node.currentSrc);
        }
        if (node.querySelectorAll) {
            var els = node.querySelectorAll('video,source,audio');
            for (var i = 0; i < els.length; i++) {
                if (els[i].src) addUrl(els[i].src);
                if (els[i].currentSrc) addUrl(els[i].currentSrc);
            }
        }
    }

    var observer = new MutationObserver(function(mutations) {
        for (var i = 0; i < mutations.length; i++) {
            var nodes = mutations[i].addedNodes;
            for (var j = 0; j < nodes.length; j++) {
                scanNode(nodes[j]);
            }
        }
    });
    observer.observe(document.documentElement || document.body,
                     {childList: true, subtree: true});

    // Scanner les éléments déjà présents
    var existing = document.querySelectorAll('video,source,audio');
    for (var k = 0; k < existing.length; k++) {
        if (existing[k].src) addUrl(existing[k].src);
        if (existing[k].currentSrc) addUrl(existing[k].currentSrc);
    }
})();
"""

# User-agents
_UA_DESKTOP = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def _resolve_redirect(url: str, referer: str | None = None) -> str:
    """
    Suit les redirections HTTP et tente d'extraire l'URL du média depuis
    un éventuel JSON de réponse (ex : endpoint /register/).
    """
    try:
        req = urllib.request.Request(url)
        req.add_header("User-Agent", _UA_DESKTOP)
        if referer:
            req.add_header("Referer", referer)
        req.add_header("Accept", "*/*")
        with urllib.request.urlopen(req, timeout=8) as resp:
            final_url = resp.url
            content_type = resp.headers.get("Content-Type", "")
            body = resp.read(4096)  # lire au max 4 Ko

        # Si la réponse est JSON, chercher une URL média dedans
        if "json" in content_type or body.lstrip().startswith(b"{"):
            try:
                data = json.loads(body)
                found = _find_media_url(data)
                if found:
                    return found
            except Exception:
                pass

        return final_url
    except Exception:
        return url


def _find_media_url(obj) -> str | None:
    """Cherche récursivement la première URL http(s) dans un objet JSON."""
    if isinstance(obj, str):
        if obj.startswith("http") and any(
            ext in obj.lower() for ext in (".mp3", ".mp4", ".m4a", ".webm", ".ogg",
                                            ".aac", ".wav", ".flac", ".m3u8", ".mpd")
        ):
            return obj
        return None
    if isinstance(obj, dict):
        for v in obj.values():
            found = _find_media_url(v)
            if found:
                return found
    if isinstance(obj, list):
        for item in obj:
            found = _find_media_url(item)
            if found:
                return found
    return None


_MEDIA_EXTENSIONS = (
    ".mp4", ".m4v", ".webm", ".mkv", ".flv", ".mov",
    ".m3u8", ".mpd", ".ts",
    ".mp3", ".aac", ".ogg", ".wav", ".opus", ".m4a",
)


def _is_media_url(url: str) -> bool:
    """Filtre les URLs réseau pour ne garder que les médias."""
    low = url.lower().split("?")[0].split("#")[0]
    return any(low.endswith(ext) for ext in _MEDIA_EXTENSIONS)


def _url_type(url: str) -> str:
    low = url.lower().split("?")[0].split("#")[0]
    if ".m3u8" in low:
        return "HLS"
    if ".mpd" in low:
        return "DASH"
    for ext in (".mp4", ".m4v", ".webm", ".mkv", ".flv", ".mov"):
        if low.endswith(ext):
            return f"Vidéo {ext[1:].upper()}"
    for ext in (".mp3", ".aac", ".ogg", ".wav", ".opus"):
        if low.endswith(ext):
            return f"Audio {ext[1:].upper()}"
    return "Média"


class UGEDialog(wx.Frame):
    """
    Fenêtre d'extraction guidée.
    Ouvre un vrai navigateur Chrome (DrissionPage) à côté de la fenêtre
    DownAccess qui affiche les médias détectés.
    100 % accessible NVDA.
    """

    def __init__(self, parent, on_add_url):
        super().__init__(
            parent,
            title="Extraction guidée — DownAccess",
            style=wx.DEFAULT_FRAME_STYLE,
        )
        self._on_add_url = on_add_url
        self._detected: list[str] = []
        self._poll_timer = wx.Timer(self)
        self._page = None  # DrissionPage ChromiumPage
        self._polling = False

        self._build_ui()
        self._bind_events()
        self.SetSize((500, 600))
        self.Centre()

        speech.speak(
            "Extraction guidée ouverte. "
            "Saisissez une URL et appuyez sur Entrée pour naviguer. "
            "Lancez la vidéo dans le navigateur Chrome qui s'est ouvert. "
            "Les médias détectés apparaîtront dans cette fenêtre. "
            "Note : les contenus protégés par DRM (Netflix, Disney+, Prime Video) ne sont pas pris en charge.",
        )

    # ------------------------------------------------------------------
    # Construction de l'UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Barre d'adresse
        addr_sizer = wx.BoxSizer(wx.HORIZONTAL)
        lbl_addr = wx.StaticText(panel, label="Adresse :")
        self.txt_url = wx.TextCtrl(
            panel,
            name="Adresse URL",
            style=wx.TE_PROCESS_ENTER,
        )
        self.txt_url.SetHint("https://www.example.com/video")
        self.btn_go = wx.Button(panel, label="Aller", name="Aller à l'adresse")

        addr_sizer.Add(lbl_addr,     0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        addr_sizer.Add(self.txt_url, 1, wx.EXPAND | wx.RIGHT, 6)
        addr_sizer.Add(self.btn_go,  0)
        sizer.Add(addr_sizer, 0, wx.EXPAND | wx.ALL, 8)

        # Statut
        self.lbl_status = wx.StaticText(
            panel,
            label="Entrez une URL pour ouvrir le navigateur.",
        )
        sizer.Add(self.lbl_status, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        # Liste des médias détectés
        lbl_detected = wx.StaticText(panel, label="Médias détectés :")
        self.lst_media = wx.ListCtrl(
            panel,
            style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.LC_HRULES | wx.BORDER_SUNKEN,
            name="Liste des médias détectés",
        )
        self.lst_media.InsertColumn(0, "Type", width=90)
        self.lst_media.InsertColumn(1, "URL", width=360)

        self.lbl_count = wx.StaticText(panel, label="0 média(s) détecté(s)")

        sizer.Add(lbl_detected,   0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
        sizer.Add(self.lst_media, 1, wx.EXPAND | wx.ALL, 6)
        sizer.Add(self.lbl_count, 0, wx.LEFT | wx.BOTTOM, 8)

        # Boutons
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_clear = wx.Button(
            panel, label="Effacer",
            name="Effacer la liste des médias détectés",
        )
        self.btn_add = wx.Button(
            panel, label="Ajouter à la file",
            name="Ajouter le média sélectionné à la file de téléchargement",
        )
        self.btn_add.Disable()
        self.btn_close = wx.Button(panel, wx.ID_CLOSE, label="Fermer")

        btn_sizer.Add(self.btn_clear, 0, wx.RIGHT, 6)
        btn_sizer.Add(self.btn_add,   1, wx.RIGHT, 6)
        btn_sizer.Add(self.btn_close, 0)
        sizer.Add(btn_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        panel.SetSizer(sizer)
        self.txt_url.SetFocus()

    # ------------------------------------------------------------------
    # Liaison des événements
    # ------------------------------------------------------------------

    def _bind_events(self) -> None:
        self.btn_go.Bind(wx.EVT_BUTTON, self._on_go)
        self.txt_url.Bind(wx.EVT_TEXT_ENTER, self._on_go)
        self.btn_clear.Bind(wx.EVT_BUTTON, self._on_clear)
        self.btn_add.Bind(wx.EVT_BUTTON, self._on_add)
        self.btn_close.Bind(wx.EVT_BUTTON, lambda _: self.Close())
        self.lst_media.Bind(wx.EVT_LIST_ITEM_SELECTED, self._on_media_select)
        self.lst_media.Bind(wx.EVT_LIST_ITEM_DESELECTED, self._on_media_deselect)
        self.lst_media.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self._on_media_activate)
        self.lst_media.Bind(wx.EVT_KEY_DOWN, self._on_list_key)
        self.Bind(wx.EVT_TIMER, self._on_poll, self._poll_timer)
        self.Bind(wx.EVT_CLOSE, self._on_close)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _ensure_browser(self) -> bool:
        """Lance le navigateur Chromium (Chrome, Edge ou Brave) si pas encore ouvert."""
        if self._page is not None:
            return True

        browser_path = find_browser()
        if not browser_path:
            wx.MessageBox(
                "Aucun navigateur compatible trouvé.\n\n"
                "Installez Google Chrome, Microsoft Edge ou Brave.",
                "Erreur — Extraction guidée",
                wx.OK | wx.ICON_ERROR,
                self,
            )
            return False

        try:
            from DrissionPage import ChromiumPage, ChromiumOptions
            co = ChromiumOptions()
            co.set_browser_path(browser_path)
            co.auto_port()
            self._page = ChromiumPage(co)
            self._browser_name = browser_name(browser_path)
            # Écouter toutes les requêtes réseau (filtrage côté Python)
            self._page.listen.start('')
            return True
        except Exception as exc:
            _log.error("Impossible d'ouvrir le navigateur : %s", exc)
            wx.MessageBox(
                f"Impossible d'ouvrir le navigateur.\n\n{exc}",
                "Erreur — Extraction guidée",
                wx.OK | wx.ICON_ERROR,
                self,
            )
            return False

    def _on_go(self, _event) -> None:
        url = self.txt_url.GetValue().strip()
        if not url:
            return
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
            self.txt_url.SetValue(url)

        if not self._ensure_browser():
            return

        self.lbl_status.SetLabel("Chargement…")

        def navigate():
            try:
                self._page.get(url)
                # Injecter le script de détection de médias
                self._page.run_js(_MONITOR_SCRIPT)
                current_url = self._page.url
                title = self._page.title
                wx.CallAfter(self._on_page_loaded, current_url, title)
            except Exception as exc:
                _log.error("Erreur navigation : %s", exc)
                wx.CallAfter(
                    self.lbl_status.SetLabel,
                    f"Erreur : {exc}",
                )

        threading.Thread(target=navigate, daemon=True).start()

    def _on_page_loaded(self, url: str, title: str) -> None:
        self.txt_url.SetValue(url)
        self.lbl_status.SetLabel(
            f"Page chargée : {title}\n"
            "Lancez la vidéo dans Chrome — les médias seront détectés automatiquement."
        )
        if not self._poll_timer.IsRunning():
            self._poll_timer.Start(1000)

    # ------------------------------------------------------------------
    # Polling JS → détection des médias
    # ------------------------------------------------------------------

    def _on_poll(self, _event) -> None:
        if self._page is None or self._polling:
            return
        self._polling = True

        def poll():
            try:
                found_urls = []

                # 1. Requêtes réseau capturées (iframes inclus)
                for packet in self._page.listen.steps(timeout=0.5):
                    url = packet.url if hasattr(packet, 'url') else str(packet)
                    if url and _is_media_url(url):
                        found_urls.append(url)

                # 2. Script JS sur la page principale (XHR/fetch/DOM)
                try:
                    self._page.run_js(_MONITOR_SCRIPT)
                    data = self._page.run_js("JSON.stringify(window.__da_urls || [])")
                    if data:
                        found_urls.extend(json.loads(data))
                except Exception:
                    pass

                current_url = self._page.url
                wx.CallAfter(self._update_detected, found_urls, current_url)
            except Exception as exc:
                _log.debug("Polling error: %s", exc)
            finally:
                self._polling = False

        threading.Thread(target=poll, daemon=True).start()

    def _update_detected(self, urls: list, current_url: str) -> None:
        self.txt_url.SetValue(current_url)

        added = 0
        for url in urls:
            if url not in self._detected:
                self._detected.append(url)
                media_type = _url_type(url)
                idx = self.lst_media.GetItemCount()
                self.lst_media.InsertItem(idx, media_type)
                self.lst_media.SetItem(idx, 1, url)
                added += 1

        if added:
            n = self.lst_media.GetItemCount()
            self.lbl_count.SetLabel(f"{n} média(s) détecté(s)")
            speech.speak(
                f"{added} média{'s' if added > 1 else ''} détecté{'s' if added > 1 else ''}.",
                interrupt=False,
            )

    # ------------------------------------------------------------------
    # Gestion de la liste des médias
    # ------------------------------------------------------------------

    def _on_media_select(self, event) -> None:
        self.btn_add.Enable()
        event.Skip()

    def _on_media_deselect(self, _event) -> None:
        if self.lst_media.GetFirstSelected() == -1:
            self.btn_add.Disable()

    def _on_media_activate(self, _event) -> None:
        self._on_add(None)

    def _on_list_key(self, event) -> None:
        if event.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self._on_add(None)
        else:
            event.Skip()

    def _on_clear(self, _event) -> None:
        self._detected.clear()
        self.lst_media.DeleteAllItems()
        self.lbl_count.SetLabel("0 média(s) détecté(s)")
        self.btn_add.Disable()
        speech.speak("Liste effacée.")

    def _on_add(self, _event) -> None:
        idx = self.lst_media.GetFirstSelected()
        if idx == -1:
            return
        url = self.lst_media.GetItemText(idx, 1)
        # Normaliser les paramètres de consentement connus
        url = url.replace("accepted=false", "accepted=true")

        # Récupérer le referer et les cookies depuis Chrome
        referer = None
        cookies = None
        if self._page:
            try:
                referer = self._page.url
            except Exception:
                pass
            try:
                cookies = self._page.run_js("document.cookie")
            except Exception:
                pass

        self.btn_add.Disable()
        speech.speak("Résolution de l'URL en cours…", interrupt=False)

        def resolve_and_add():
            final_url = _resolve_redirect(url, referer)
            wx.CallAfter(self._finish_add, final_url, referer, cookies)

        threading.Thread(target=resolve_and_add, daemon=True).start()

    def _finish_add(self, url: str, referer: str | None, cookies: str | None) -> None:
        self.btn_add.Enable()
        self._on_add_url(url, referer=referer, cookies=cookies)
        speech.speak("Ajouté à la file de téléchargement.")

    # ------------------------------------------------------------------
    # Fermeture
    # ------------------------------------------------------------------

    def _on_close(self, event) -> None:
        self._poll_timer.Stop()
        # Fermer le navigateur Chrome
        if self._page:
            try:
                self._page.listen.stop()
            except Exception:
                pass
            try:
                self._page.quit()
            except Exception:
                pass
            self._page = None
        event.Skip()
