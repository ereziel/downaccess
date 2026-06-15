"""Convertit les guides utilisateur Markdown en HTML accessible et autonome.

Source  : docs/guide.md (FR), docs/guide.en.md (EN)
Sortie  : docs/guide.fr.html, docs/guide.en.html

Le HTML est embarque dans l'application (menu Aide -> Guide d'utilisation, ouvert
dans le navigateur par defaut). Les fichiers sont autonomes (CSS inline), avec une
structure semantique (titres, table des matieres) lue correctement par NVDA/JAWS.

Lancer apres toute modification des .md :
    uv run python scripts/build_docs.py
"""

import re
from pathlib import Path

import mistune

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"

# Memes regles de slug que le sommaire Markdown (ancres #...) -> liens internes OK.
_TAG_RE = re.compile(r"<[^>]+>")


def slug(text):
    s = _TAG_RE.sub("", text).lower()
    s = re.sub(r"[^\w\s-]", "", s, flags=re.UNICODE)
    return re.sub(r"\s+", "-", s.strip())


class AccessibleRenderer(mistune.HTMLRenderer):
    """Ajoute un id (ancre) sur chaque titre pour que le sommaire fonctionne."""

    def heading(self, text, level, **attrs):
        return f'<h{level} id="{slug(text)}">{text}</h{level}>\n'


_CSS = """
:root { color-scheme: light dark; }
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: "Segoe UI", system-ui, -apple-system, Arial, sans-serif;
  font-size: 1.05rem;
  line-height: 1.65;
  color: #1b1b1b;
  background: #ffffff;
}
main {
  max-width: 820px;
  margin: 0 auto;
  padding: 2rem 1.25rem 4rem;
}
h1 { font-size: 2rem; line-height: 1.2; margin: 0 0 .5rem; }
h2 {
  font-size: 1.5rem;
  margin: 2.5rem 0 .75rem;
  padding-top: .75rem;
  border-top: 2px solid #d0d0d0;
}
h3 { font-size: 1.2rem; margin: 1.75rem 0 .5rem; }
h4 { font-size: 1.05rem; margin: 1.25rem 0 .4rem; }
p, li { max-width: 70ch; }
a { color: #0b5ed7; }
a:hover { text-decoration: none; }
code {
  font-family: "Cascadia Code", Consolas, monospace;
  background: #f0f0f0;
  padding: .1em .35em;
  border-radius: 4px;
  font-size: .92em;
}
strong { font-weight: 600; }
table { border-collapse: collapse; margin: 1rem 0; width: 100%; }
th, td { border: 1px solid #c8c8c8; padding: .45rem .7rem; text-align: left; }
th { background: #f3f3f3; }
blockquote {
  margin: 1rem 0;
  padding: .25rem 1rem;
  border-left: 4px solid #0b5ed7;
  background: #f6f9ff;
}
nav ol { line-height: 1.9; }
.skip-link {
  position: absolute;
  left: -9999px;
  top: 0;
  background: #0b5ed7;
  color: #fff;
  padding: .6rem 1rem;
  z-index: 10;
}
.skip-link:focus { left: 0; }
:focus-visible { outline: 3px solid #0b5ed7; outline-offset: 2px; }
@media (prefers-color-scheme: dark) {
  body { color: #e6e6e6; background: #1e1e1e; }
  h2 { border-top-color: #444; }
  a { color: #6ea8fe; }
  code { background: #2d2d2d; }
  th { background: #2a2a2a; }
  td, th { border-color: #444; }
  blockquote { background: #23262b; border-left-color: #6ea8fe; }
}
@media print {
  .skip-link { display: none; }
  body { font-size: 12pt; }
}
"""

_TEMPLATE = """<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>{css}</style>
</head>
<body>
<a class="skip-link" href="#content">{skip}</a>
<main id="content">
{body}
</main>
</body>
</html>
"""


def _title_from(md_text, default):
    for line in md_text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return default


def build(md_name, html_name, lang, skip_label, default_title):
    md_text = (DOCS / md_name).read_text(encoding="utf-8")
    renderer = mistune.create_markdown(
        renderer=AccessibleRenderer(escape=False),
        plugins=["table", "strikethrough", "url"],
    )
    body = renderer(md_text)
    html = _TEMPLATE.format(
        lang=lang,
        title=_title_from(md_text, default_title),
        css=_CSS,
        skip=skip_label,
        body=body,
    )
    (DOCS / html_name).write_text(html, encoding="utf-8")
    print("wrote", html_name, "(", len(html), "chars )")


def main():
    build("guide.md", "guide.fr.html", "fr",
          "Aller au contenu", "Guide d'utilisation de DownAccess")
    build("guide.en.md", "guide.en.html", "en",
          "Skip to content", "DownAccess User Guide")


if __name__ == "__main__":
    main()
