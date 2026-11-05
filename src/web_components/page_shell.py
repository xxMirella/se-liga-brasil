"""Complete HTML document: skip link, header, main region and footer."""

from web_components.escaping import escape_text
from web_components.site_footer import render_site_footer
from web_components.site_header import render_site_header

SITE_NAME = "Se Liga, Brasil"
BASE_STYLESHEET = "/assets/public-profile.css"
SCROLL_REVEAL_SCRIPT = "/assets/scroll-reveal.js"


def render_page(title, content_html, *, active_section, query="", extra_stylesheet=None,
                footer_sources_html="", footer_notes_html="", scripts=()):
    extra = ""
    if extra_stylesheet:
        extra = f'<link rel="stylesheet" href="{escape_text(extra_stylesheet)}">'
    script_tags = "".join(f'<script src="{escape_text(src)}" defer></script>' for src in scripts)
    return f'''<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape_text(title)} · {SITE_NAME}</title>
<link rel="icon" type="image/svg+xml" sizes="any" href="/assets/brazil-flag.svg">
<link rel="stylesheet" href="{BASE_STYLESHEET}">{extra}{script_tags}</head>
<body><a class="ds-skip-link" href="#main">Ir para o conteúdo</a>
{render_site_header(active_section, query)}
<main id="main">{content_html}</main>
{render_site_footer(footer_sources_html, footer_notes_html)}
</body></html>'''
