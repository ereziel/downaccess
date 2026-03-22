"""
Dialogue de mise à jour de DownAccess.
Affiche la nouvelle version, les notes de release en HTML et propose de mettre à jour.

Notes NVDA :
- WebView2 + NVDA 2024.3+ : browse mode complet (H, L, touches rapides)
- Un clic simulé est injecté après chargement pour activer le browse mode
- lang="fr" sur <html> pour la voix de synthèse
"""
import ctypes

import wx
import wx.html2

from app.core import speech


def _md_to_html(md: str) -> str:
    """Convertit du Markdown en page HTML complète accessible NVDA."""
    try:
        import mistune
        body = mistune.html(md)
    except Exception:
        # Fallback : texte brut entre <pre>
        escaped = md.replace("&", "&amp;").replace("<", "&lt;")
        body = f"<pre>{escaped}</pre>"

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <style>
    body {{
      font-family: Segoe UI, Arial, sans-serif;
      font-size: 14px;
      line-height: 1.6;
      margin: 12px 16px;
      color: #1a1a1a;
      background: #ffffff;
    }}
    h1 {{ font-size: 1.2em; margin-top: 0.6em; margin-bottom: 0.4em; }}
    h2 {{ font-size: 1.1em; margin-top: 1.2em; margin-bottom: 0.3em; }}
    ul  {{ padding-left: 1.4em; margin: 0.3em 0; }}
    li  {{ margin-bottom: 0.2em; }}
    strong {{ font-weight: bold; }}
    p   {{ margin: 0.4em 0; }}
  </style>
</head>
<body>
  <main role="main">
{body}
  </main>
</body>
</html>"""


def _simulate_click(window: wx.Window) -> None:
    """
    Simule un clic gauche au centre du contrôle WebView2.
    Nécessaire pour que NVDA active son browse mode dans le WebView.
    Sans ça, NVDA reste en mode focus et ne lit pas le contenu.
    (Corrigé nativement dans NVDA 2024.3+, le clic reste inoffensif.)
    """
    try:
        rect = window.GetScreenRect()
        cx = rect.x + rect.width  // 2
        cy = rect.y + rect.height // 2
        u32 = ctypes.windll.user32
        u32.SetCursorPos(cx, cy)
        u32.mouse_event(0x0002, 0, 0, 0, 0)   # MOUSEEVENTF_LEFTDOWN
        u32.mouse_event(0x0004, 0, 0, 0, 0)   # MOUSEEVENTF_LEFTUP
    except Exception:
        pass   # Non bloquant (VM, CI, etc.)


class UpdateDialog(wx.Dialog):
    """
    Dialogue affiché quand une nouvelle version est disponible.
    Les release notes sont rendues en HTML dans un WebView2.
    Boutons : Mettre à jour maintenant / Plus tard
    """

    def __init__(self, parent, new_version: str, release_notes: str):
        super().__init__(
            parent,
            title=f"Mise à jour disponible — DownAccess {new_version}",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
            size=(600, 480),
        )
        self._html = _md_to_html(release_notes or "Aucune note disponible.")
        self._build_ui(new_version)
        self.CentreOnParent()

        # Focus sur le WebView (contenu avant bouton — règle projet)
        self._web.SetFocus()

        speech.speak(
            f"Mise à jour disponible. DownAccess {new_version} est disponible. "
            f"Appuyez sur Tab pour accéder aux boutons."
        )

    # ------------------------------------------------------------------

    def _build_ui(self, new_version: str) -> None:
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

        # Label lié au WebView (NVDA lit le label quand le focus arrive)
        lbl_notes = wx.StaticText(self, label="Notes de version :")
        sizer.Add(lbl_notes, 0, wx.LEFT | wx.RIGHT, 12)

        # WebView2
        self._web = wx.html2.WebView.New(self, name="Notes de version")
        sizer.Add(self._web, 1, wx.EXPAND | wx.ALL, 8)

        # Chargement du HTML après création du widget
        self._web.SetPage(self._html, "")

        # Activer le browse mode NVDA dès que le WebView est prêt
        self._web.Bind(wx.html2.EVT_WEBVIEW_LOADED, self._on_loaded)

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
        self.btn_update.SetDefault()
        btn_sizer.AddStretchSpacer()
        btn_sizer.Add(self.btn_update, 0, wx.RIGHT, 8)
        btn_sizer.Add(self.btn_later,  0, wx.RIGHT, 8)
        sizer.Add(btn_sizer, 0, wx.EXPAND | wx.BOTTOM, 10)

        self.SetSizer(sizer)

    def _on_loaded(self, _event) -> None:
        """Page chargée → simuler le clic pour activer le browse mode NVDA."""
        wx.CallAfter(_simulate_click, self._web)
