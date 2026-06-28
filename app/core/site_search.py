"""Recherche sur des sites sans préfixe de recherche yt-dlp (france.tv, Arte).

La recherche intégrée de DownAccess repose sur les préfixes yt-dlp
(``ytsearch:``, ``scsearch:``). france.tv et Arte n'en ont pas : on interroge
ici directement leurs API HTTP publiques, puis on normalise les résultats au
même format que les entrées yt-dlp (clés ``title``, ``id``, ``duration``,
``uploader``/``channel``, ``webpage_url``, ``_dl_type``) pour réutiliser tel
quel ``SearchResultsDialog``.

Les URL renvoyées sont des pages ``france.tv``/``arte.tv`` : elles retombent
dans le flux « sites personnalisés » (``custom_sites.is_custom_site_url`` →
choix de piste audio français / audiodescription).

Aucun `import wx` ici (règle app/core).
"""

import re
import unicodedata

from curl_cffi import requests as cffi_requests


# Endpoints de recherche (vérifiés en conditions réelles, juin 2026).
_FRANCETV_SEARCH_URL = "https://api-mobile.yatta.francetv.fr/apps/search"
# Arte : API "web" (api.arte.tv) — pas de jeton requis, contrairement à l'API "app".
_ARTE_SEARCH_URL = "https://api.arte.tv/api/emac/v4/{lang}/web/pages/SEARCH/"
_ARTE_LANGS = ("fr", "de", "en", "es", "it", "pl")

_TIMEOUT = 20


def search(site_key: str, query: str, limit: int, lang: str) -> list[dict]:
    """Recherche sur un site personnalisé.

    site_key ∈ {"francetv", "arte"}. Retourne une liste d'entrées normalisées
    (au plus ``limit``), prêtes pour ``SearchResultsDialog``.
    """
    query = (query or "").strip()
    if not query:
        return []
    if site_key == "francetv":
        return _search_francetv(query, limit)
    if site_key == "arte":
        return _search_arte(query, limit, lang)
    return []


def _slugify(text: str) -> str:
    """Slug ASCII minimal pour l'URL france.tv (la valeur exacte est ignorée
    par le site, seul le chemin du programme + l'id numérique comptent)."""
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text or "video"


def _search_francetv(query: str, limit: int) -> list[dict]:
    """Recherche france.tv via l'API mobile (collection « Vidéos »).

    Seules les vidéos directement téléchargeables (type ``playlist_video``)
    sont retournées : yt-dlp ne sait pas extraire une page de programme
    (série) france.tv, on n'expose donc pas les programmes/collections.
    """
    resp = cffi_requests.get(
        _FRANCETV_SEARCH_URL,
        params={"platform": "apps", "filters": "with-collections", "term": query},
        impersonate="chrome",
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()

    entries: list[dict] = []
    for collection in data.get("collections", []):
        if collection.get("type") != "playlist_video":
            continue
        for item in collection.get("items", []):
            vid_id = item.get("id")
            si_id = item.get("si_id")
            if not vid_id and not si_id:
                continue
            program = item.get("program") or {}
            program_path = program.get("program_path") or ""
            title = item.get("title") or item.get("episode_title") or program.get("label") or "?"

            if program_path and vid_id:
                # URL web réelle : la slug est ignorée par france.tv, seuls le
                # chemin du programme et l'id numérique sont déterminants.
                web_path = program_path.replace("_", "/")
                url = f"https://www.france.tv/{web_path}/{vid_id}-{_slugify(title)}.html"
            elif si_id:
                # Repli : schéma interne yt-dlp (toujours téléchargeable).
                url = f"francetv:{si_id}"
            else:
                continue

            entries.append({
                "title": title,
                "id": str(si_id or vid_id),
                "duration": item.get("duration"),
                "uploader": program.get("label") or item.get("offer") or "france.tv",
                "webpage_url": url,
                "_dl_type": "video",
            })
            if len(entries) >= limit:
                return entries
    return entries


def _search_arte(query: str, limit: int, lang: str) -> list[dict]:
    """Recherche Arte via l'API web EMAC v4 (zone « Toutes les vidéos »).

    Les collections (séries, magazines) sont incluses : leur URL est une page
    arte.tv que yt-dlp développe en playlist. Les vidéos unitaires gardent le
    flux normal (choix de piste audio).
    """
    arte_lang = lang if lang in _ARTE_LANGS else "fr"
    resp = cffi_requests.get(
        _ARTE_SEARCH_URL.format(lang=arte_lang),
        params={"query": query, "page": 1, "limit": max(limit, 10)},
        impersonate="chrome",
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()

    entries: list[dict] = []
    for zone in data.get("zones", []):
        if zone.get("code") != "listing_SEARCH":
            continue
        for item in (zone.get("content") or {}).get("data", []):
            url = item.get("url")
            if not url or "arte.tv" not in url:
                continue  # ignore les liens externes (kind EXTERNAL)
            kind = item.get("kind") or {}
            is_collection = bool(kind.get("isCollection"))
            title = item.get("title") or "?"
            subtitle = item.get("subtitle")
            entries.append({
                "title": f"{title} — {subtitle}" if subtitle else title,
                "id": str(item.get("id") or url),
                "duration": item.get("duration"),
                "uploader": "Arte",
                "webpage_url": url,
                "_dl_type": "playlist" if is_collection else "video",
            })
            if len(entries) >= limit:
                return entries
    return entries
