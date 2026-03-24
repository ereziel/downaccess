"""
Extraction Guidée (User Guided Extraction)

L'utilisateur navigue dans un navigateur intégré.
Un script JS intercepte toutes les requêtes XHR/fetch et les éléments
<video>/<source> pour détecter les URLs de médias en temps réel.
L'utilisateur joue la vidéo puis ajoute le média détecté à la file.
"""
import json
import os
import threading
import urllib.request
from pathlib import Path

import wx
import wx.html2

from app.core import speech

# ------------------------------------------------------------------
# Script JS injecté après chaque chargement de page
# ------------------------------------------------------------------

_F6_SCRIPT = r"""
(function() {
    if (window.__da_f6) return;
    window.__da_f6 = true;
    document.addEventListener('keydown', function(e) {
        if (e.key === 'F6' && !e.ctrlKey && !e.altKey && !e.shiftKey) {
            e.preventDefault();
            e.stopPropagation();
            window.location.assign('downaccess://f6');
        }
    }, true);
})();
"""

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
            node.querySelectorAll('video,source,audio').forEach(function(el) {
                if (el.src) addUrl(el.src);
                if (el.currentSrc) addUrl(el.currentSrc);
            });
        }
    }

    var observer = new MutationObserver(function(mutations) {
        mutations.forEach(function(m) {
            m.addedNodes.forEach(scanNode);
        });
    });
    observer.observe(document.documentElement || document.body,
                     {childList: true, subtree: true});

    // Scanner les éléments déjà présents
    document.querySelectorAll('video,source,audio').forEach(function(el) {
        if (el.src) addUrl(el.src);
        if (el.currentSrc) addUrl(el.currentSrc);
    });
})();
"""

# User-agents
_UA_DESKTOP = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
_UA_MOBILE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/17.0 Mobile/15E148 Safari/604.1"
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
    Non-modale : l'utilisateur navigue et les médias s'ajoutent en direct.
    100 % accessible NVDA.
    """

    def __init__(self, parent, on_add_url):
        # Profil WebView2 persistant → cookies conservés entre sessions (Cloudflare, auth…)
        profile_dir = Path(os.environ.get("APPDATA", "")) / "DownAccess" / "WebView2Profile"
        profile_dir.mkdir(parents=True, exist_ok=True)
        os.environ["WEBVIEW2_USER_DATA_FOLDER"] = str(profile_dir)

        super().__init__(
            parent,
            title="Extraction guidée — DownAccess",
            style=wx.DEFAULT_FRAME_STYLE,
        )
        self._on_add_url = on_add_url
        self._detected: list[str] = []
        self._poll_timer = wx.Timer(self)

        self._build_ui()
        self._bind_events()
        self.SetMinSize((900, 580))
        self.Maximize()

        speech.speak(
            "Extraction guidée ouverte. "
            "Saisissez une URL et appuyez sur Entrée pour naviguer. "
            "Lancez la vidéo sur la page. "
            "Appuyez sur F6 pour basculer vers la liste des médias. "
            "Utilisez Tab pour naviguer entre les boutons et appuyez sur Entrée pour les activer.",
        )

    # ------------------------------------------------------------------
    # Construction de l'UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # ---- Partie gauche : navigateur ----
        left_sizer = wx.BoxSizer(wx.VERTICAL)

        # Barre d'adresse
        addr_panel = wx.Panel(panel)
        addr_sizer = wx.BoxSizer(wx.HORIZONTAL)

        lbl_addr = wx.StaticText(addr_panel, label="Adresse :")
        self.txt_url = wx.TextCtrl(
            addr_panel,
            name="Adresse URL",
            style=wx.TE_PROCESS_ENTER,
        )
        self.txt_url.SetHint("https://www.example.com/video")
        self.btn_go = wx.Button(addr_panel, label="Aller", name="Aller à l'adresse")

        lbl_ua = wx.StaticText(addr_panel, label="Mode :")
        self.choice_ua = wx.Choice(
            addr_panel,
            choices=["Bureau", "Mobile (iPhone)"],
            name="Mode navigateur",
        )
        self.choice_ua.SetSelection(0)

        addr_sizer.Add(lbl_addr,       0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT | wx.RIGHT, 6)
        addr_sizer.Add(self.txt_url,   1, wx.EXPAND | wx.RIGHT, 6)
        addr_sizer.Add(self.btn_go,    0, wx.RIGHT, 12)
        addr_sizer.Add(lbl_ua,         0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        addr_sizer.Add(self.choice_ua, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        addr_panel.SetSizer(addr_sizer)

        # Navigateur
        self.browser = wx.html2.WebView.New(panel)
        self.browser.SetName("Navigateur intégré")

        # Statut du navigateur
        self.lbl_nav_status = wx.StaticText(panel, label="")

        left_sizer.Add(addr_panel,          0, wx.EXPAND | wx.ALL, 6)
        left_sizer.Add(self.browser,        1, wx.EXPAND)
        left_sizer.Add(self.lbl_nav_status, 0, wx.EXPAND | wx.LEFT | wx.BOTTOM, 6)

        # ---- Partie droite : médias détectés ----
        right_sizer = wx.BoxSizer(wx.VERTICAL)

        lbl_detected = wx.StaticText(panel, label="Médias détectés :")
        self.lst_media = wx.ListCtrl(
            panel,
            style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.LC_HRULES | wx.BORDER_SUNKEN,
            name="Liste des médias détectés",
        )
        self.lst_media.InsertColumn(0, "Type",  width=90)
        self.lst_media.InsertColumn(1, "URL",   width=260)

        self.lbl_count = wx.StaticText(panel, label="0 média(s) détecté(s)")

        self.btn_clear = wx.Button(
            panel, label="Effacer la liste",
            name="Effacer la liste des médias détectés",
        )
        self.btn_add = wx.Button(
            panel, label="Ajouter à la file",
            name="Ajouter le média sélectionné à la file de téléchargement",
        )
        self.btn_add.Disable()
        self.btn_close = wx.Button(panel, wx.ID_CLOSE, label="Fermer")

        right_sizer.Add(lbl_detected,   0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
        right_sizer.Add(self.lst_media, 1, wx.EXPAND | wx.ALL, 6)
        right_sizer.Add(self.lbl_count, 0, wx.LEFT | wx.BOTTOM, 8)
        right_sizer.Add(self.btn_clear, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)
        right_sizer.Add(self.btn_add,   0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)
        right_sizer.Add(self.btn_close, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)

        main_sizer.Add(left_sizer,  3, wx.EXPAND)
        main_sizer.Add(right_sizer, 1, wx.EXPAND)
        panel.SetSizer(main_sizer)

        self.txt_url.SetFocus()

    # ------------------------------------------------------------------
    # Liaison des événements
    # ------------------------------------------------------------------

    def _bind_events(self) -> None:
        self.btn_go.Bind(wx.EVT_BUTTON,           self._on_go)
        self.txt_url.Bind(wx.EVT_TEXT_ENTER,      self._on_go)
        self.choice_ua.Bind(wx.EVT_CHOICE,        self._on_ua_change)
        self.btn_clear.Bind(wx.EVT_BUTTON,        self._on_clear)
        self.btn_add.Bind(wx.EVT_BUTTON,          self._on_add)
        self.btn_close.Bind(wx.EVT_BUTTON,        lambda _: self.Close())
        self.lst_media.Bind(wx.EVT_LIST_ITEM_SELECTED,   self._on_media_select)
        self.lst_media.Bind(wx.EVT_LIST_ITEM_DESELECTED, self._on_media_deselect)
        self.lst_media.Bind(wx.EVT_LIST_ITEM_ACTIVATED,  self._on_media_activate)
        # Entrée dans la liste = ajouter à la file (redondant avec ACTIVATED mais plus fiable NVDA)
        self.lst_media.Bind(wx.EVT_KEY_DOWN, self._on_list_key)
        self.browser.Bind(wx.html2.EVT_WEBVIEW_NAVIGATING, self._on_navigating)
        self.browser.Bind(wx.html2.EVT_WEBVIEW_LOADED,    self._on_page_loaded)
        self.Bind(wx.EVT_TIMER, self._on_poll, self._poll_timer)
        self.Bind(wx.EVT_CLOSE, self._on_close)

        # F6 côté Python : fonctionne quand le focus est hors du WebView
        _ID_F6 = wx.NewIdRef()
        accel = wx.AcceleratorTable([
            (wx.ACCEL_NORMAL, wx.WXK_F6, _ID_F6),
        ])
        self.SetAcceleratorTable(accel)
        self.Bind(wx.EVT_MENU, self._on_f6, id=_ID_F6)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _on_f6(self, _event) -> None:
        """F6 : cycle barre d'adresse → navigateur → liste des médias → barre d'adresse."""
        focused = self.FindFocus()
        if focused is self.txt_url or focused is self.btn_go or focused is self.choice_ua:
            self.browser.SetFocus()
            speech.speak("Navigateur.", interrupt=True)
        elif focused is self.browser:
            if self.lst_media.GetItemCount() > 0:
                self.lst_media.SetFocus()
                if self.lst_media.GetFirstSelected() == -1:
                    self.lst_media.Select(0)
                    self.lst_media.Focus(0)
                speech.speak("Liste des médias.", interrupt=True)
            else:
                self.txt_url.SetFocus()
                speech.speak("Barre d'adresse.", interrupt=True)
        else:
            self.txt_url.SetFocus()
            speech.speak("Barre d'adresse.", interrupt=True)

    def _on_go(self, _event) -> None:
        url = self.txt_url.GetValue().strip()
        if not url:
            return
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
            self.txt_url.SetValue(url)
        self.browser.LoadURL(url)

    def _on_navigating(self, event) -> None:
        url = event.GetURL()
        # Intercepter la commande F6 envoyée depuis le JS du navigateur
        if url == "downaccess://f6":
            event.Veto()
            self._on_f6(None)
            return
        self.txt_url.SetValue(url)
        self.lbl_nav_status.SetLabel("Chargement…")
        event.Skip()

    def _on_page_loaded(self, _event) -> None:
        # Ne pas injecter les scripts sur about:blank ou pages spéciales
        try:
            current_url = self.browser.GetCurrentURL()
        except Exception:
            current_url = ""
        if not current_url or current_url in ("about:blank", "") or current_url.startswith("edge://"):
            return
        self.lbl_nav_status.SetLabel("Page chargée — lancez la vidéo pour détecter les médias.")
        self.browser.RunScript(_F6_SCRIPT)
        self.browser.RunScript(_MONITOR_SCRIPT)
        if not self._poll_timer.IsRunning():
            self._poll_timer.Start(600)

    def _on_ua_change(self, _event) -> None:
        ua = _UA_MOBILE if self.choice_ua.GetSelection() == 1 else _UA_DESKTOP
        # Injecter le User-Agent via JS (configurable pour permettre les changements suivants)
        self.browser.RunScript(
            f"Object.defineProperty(navigator, 'userAgent', "
            f"{{get: () => '{ua}', configurable: true}});"
        )
        # Recharger la page pour appliquer le nouveau User-Agent
        try:
            current_url = self.browser.GetCurrentURL()
            if current_url and current_url not in ("about:blank", ""):
                self.browser.LoadURL(current_url)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Polling JS → détection des médias
    # ------------------------------------------------------------------

    def _on_poll(self, _event) -> None:
        try:
            raw = self.browser.RunScript("JSON.stringify(window.__da_urls || [])")
            # RunScript retourne (bool, str) ou str selon la version wxPython
            data = raw[1] if isinstance(raw, tuple) else raw
            urls = json.loads(data or "[]")
        except Exception:
            return

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
        referer = self.browser.GetCurrentURL() or None
        # Récupérer les cookies non-HttpOnly via JS
        cookies = None
        try:
            raw = self.browser.RunScript("document.cookie")
            val = raw[1] if isinstance(raw, tuple) else raw
            if val and val.strip():
                cookies = val.strip()
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
        event.Skip()
