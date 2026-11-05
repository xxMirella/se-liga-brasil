"""Footer with an optional "Fontes e método" disclosure and page-specific notes (trusted HTML)."""

from web_components.elements import render_disclosure

FOOTER_NOTE = "Se Liga, Brasil · Consulta pública · Dados oficiais com cobertura explicitada"


def render_site_footer(sources_html="", notes_html=""):
    sources = render_disclosure("Fontes e método", sources_html) if sources_html else ""
    return (
        '<footer class="ds-site-footer"><div class="ds-container ds-site-footer__inner">'
        f'{sources}{notes_html}<span class="ds-site-footer__note">{FOOTER_NOTE}</span>'
        "</div></footer>"
    )
