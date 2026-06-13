"""
Détection du navigateur Chromium disponible sur le système.
Utilisé par l'extraction guidée et le dialogue de connexion.
"""
import os
import socket
import time
from collections.abc import Callable

from app.core.i18n import _translate


class ConsentRequiredError(Exception):
    """Levée quand YouTube redirige vers la page de consentement / connexion
    pendant la récolte d'une playlist (profil dédié sans consentement accepté).
    L'UI la convertit en parcours de connexion guidée."""


def _free_port() -> int:
    """Trouve un port TCP local libre (pour le débogage Chrome dédié)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]



# Chemins classiques Windows (Chrome → Edge → Brave)
_CANDIDATES = [
    # Chrome
    os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
    os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
    os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
    # Edge (présent sur tout Windows 10/11)
    os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
    os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
    # Brave
    os.path.expandvars(r"%ProgramFiles%\BraveSoftware\Brave-Browser\Application\brave.exe"),
    os.path.expandvars(r"%LocalAppData%\BraveSoftware\Brave-Browser\Application\brave.exe"),
]


def find_browser() -> str | None:
    """Retourne le chemin du premier navigateur Chromium trouvé, ou None."""
    for path in _CANDIDATES:
        if os.path.isfile(path):
            return path
    return None


def browser_name(path: str) -> str:
    """Retourne un nom lisible à partir du chemin de l'exécutable."""
    low = path.lower()
    if "chrome" in low:
        return "Chrome"
    if "edge" in low or "msedge" in low:
        return "Edge"
    if "brave" in low:
        return "Brave"
    return "Navigateur"


def downaccess_profile_dir() -> str:
    """Dossier de profil navigateur dédié à DownAccess (persistant).

    L'utilisateur s'y connecte une seule fois via le dialogue de connexion ;
    les cookies y sont conservés et relus par yt-dlp (cookiesfrombrowser).
    Profil isolé = aucun conflit avec le navigateur habituel de l'utilisateur,
    qu'il soit ouvert ou non.
    """
    appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(appdata, "DownAccess", "BrowserProfile")


def open_dedicated_browser(url: str):
    """Lance le navigateur dédié à DownAccess (profil isolé persistant) et
    navigue vers `url`. Retourne l'objet ChromiumPage de DrissionPage.

    Lève RuntimeError (message traduit) si aucun navigateur compatible.
    Le profil dédié n'entre jamais en conflit avec le navigateur habituel de
    l'utilisateur, qu'il soit ouvert ou non.
    """
    bp = find_browser()
    if not bp:
        raise RuntimeError(_translate(
            "Aucun navigateur compatible trouvé.\n"
            "Installez Google Chrome, Microsoft Edge ou Brave."
        ))
    from DrissionPage import ChromiumOptions, ChromiumPage
    co = ChromiumOptions()
    co.set_browser_path(bp)
    # Profil dédié et PERSISTANT (l'utilisateur reste connecté d'une fois sur
    # l'autre). NE PAS utiliser auto_port() : il écrase set_user_data_path() par
    # un dossier temporaire qu'il supprime à la déconnexion (cf. DrissionPage
    # handle_options / _on_disconnect) -> le profil dédié ne persisterait jamais.
    # On choisit donc un port libre nous-mêmes + un user-data-path fixe ; le port
    # distinct permet de coexister avec le navigateur habituel de l'utilisateur.
    co.set_user_data_path(downaccess_profile_dir())
    co.set_local_port(_free_port())
    page = ChromiumPage(co)
    page.get(url)
    return page


def harvest_cookies(page) -> list[dict]:
    """Récolte TOUS les cookies de la session navigateur via CDP.

    `all_domains=True` est indispensable : l'authentification YouTube s'étend
    sur `.youtube.com` ET `.google.com`. `all_info=True` fournit les champs
    complets (domain, path, expires, httpOnly, secure, session).
    """
    raw = page.cookies(all_domains=True, all_info=True)
    return [dict(c) for c in raw]


def harvest_cookies_headless() -> list[dict]:
    """Récolte les cookies du profil dédié SANS fenêtre visible.

    Repli quand la fenêtre de connexion a été fermée avant la récolte : comme
    le profil dédié est persistant, la connexion y est conservée. À n'appeler
    qu'une fois la fenêtre visible fermée (un seul accès au profil à la fois).
    """
    bp = find_browser()
    if not bp:
        raise RuntimeError(_translate(
            "Aucun navigateur compatible trouvé.\n"
            "Installez Google Chrome, Microsoft Edge ou Brave."
        ))
    from DrissionPage import ChromiumOptions, ChromiumPage
    co = ChromiumOptions()
    co.set_browser_path(bp)
    co.set_user_data_path(downaccess_profile_dir())
    co.set_local_port(_free_port())
    co.headless()
    page = ChromiumPage(co)
    try:
        return harvest_cookies(page)
    finally:
        try:
            page.quit()
        except Exception:
            pass


# JS : compte les ID de vidéo uniques actuellement chargés dans la page.
_JS_COUNT = (
    'return new Set(Array.from(document.querySelectorAll("a"))'
    '.map(a=>a.href).filter(h=>h&&h.indexOf("watch?v=")>=0)'
    '.map(h=>(h.match(/[?&]v=([^&]+)/)||[])[1]).filter(Boolean)).size;'
)

# JS : extrait les entrées ORDONNEES {id,title}. On itère les blocs vidéo
# (yt-lockup-view-model) — ce qui exclut le bouton « Tout lire » — et, dans chaque
# bloc, on prend le lien-TITRE (celui qui porte un aria-label ; sa vignette voisine
# n'a que la durée comme texte). Repli : le lien watch le plus long du bloc.
_JS_EXTRACT = (
    "var out=[],seen={};"
    "document.querySelectorAll('yt-lockup-view-model').forEach(function(el){"
    "var links=el.querySelectorAll('a[href*=\"watch?v=\"]');"
    "if(!links.length)return;"
    "var id=(links[0].href.match(/[?&]v=([^&]+)/)||[])[1];"
    "if(!id||seen[id])return;seen[id]=1;"
    "var title='';"
    "for(var i=0;i<links.length;i++){if(links[i].getAttribute('aria-label')){"
    "title=(links[i].textContent||'').trim();break;}}"
    "if(!title){for(var j=0;j<links.length;j++){var t=(links[j].textContent||'').trim();"
    "if(t.length>title.length)title=t;}}"
    "out.push({id:id,title:title});});"
    "return out;"
)


def harvest_youtube_playlist(
    url: str,
    on_progress: Callable[[int], None] | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> list[dict]:
    """Récupère TOUTES les entrées d'une playlist YouTube via un vrai navigateur.

    Contourne le plafond de yt-dlp (100/200 sur les playlists non connectées) :
    charge la page dans Chrome headless (profil dédié, déjà consenti/connecté) et
    scrolle jusqu'au bout pour forcer le chargement paresseux de toutes les vidéos.

    on_progress(n) : appelé avec le nombre d'ID trouvés à chaque palier.
    should_stop()  : si fourni et renvoie True, interrompt et retourne l'acquis.
    Lève ConsentRequiredError si YouTube redirige vers la page de consentement
    (profil sans consentement) -> l'UI bascule sur la connexion guidée.

    Retourne une liste ordonnée de dicts {id, title, url} (format compatible
    PlaylistDialog et la remise en file).
    """
    bp = find_browser()
    if not bp:
        raise RuntimeError(_translate(
            "Aucun navigateur compatible trouvé.\n"
            "Installez Google Chrome, Microsoft Edge ou Brave."
        ))
    from DrissionPage import ChromiumOptions, ChromiumPage
    co = ChromiumOptions()
    co.set_browser_path(bp)
    co.set_user_data_path(downaccess_profile_dir())
    co.set_local_port(_free_port())
    co.headless()
    co.set_argument("--mute-audio")
    page = ChromiumPage(co)
    try:
        page.get(url)
        time.sleep(3)
        if "consent." in (page.url or ""):
            raise ConsentRequiredError(page.url)

        last = -1
        stable = 0
        # Borne haute généreuse (playlists géantes) ; l'arrêt réel vient de la
        # stabilité du compte ou de should_stop().
        for _i in range(600):
            if should_stop and should_stop():
                break
            try:
                n = int(page.run_js(_JS_COUNT) or 0)
            except Exception:
                n = last
            if on_progress:
                on_progress(n)
            stable = stable + 1 if n == last else 0
            last = n
            if stable >= 5:
                break
            page.run_js("window.scrollTo(0, document.documentElement.scrollHeight*2);")
            time.sleep(1.0)

        raw = page.run_js(_JS_EXTRACT) or []
        entries = []
        for item in raw:
            vid = (item or {}).get("id")
            if not vid:
                continue
            title = (item.get("title") or "").strip() or vid
            entries.append({
                "id": vid,
                "title": title,
                "url": f"https://www.youtube.com/watch?v={vid}",
            })
        return entries
    finally:
        try:
            page.quit()
        except Exception:
            pass
