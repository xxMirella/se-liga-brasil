"""Header with brand, name search and a script-free menu (a `details` disclosure)."""

from web_components.escaping import escape_text
from web_components.navigation import render_site_navigation


def render_site_header(active_section, query=""):
    return f'''<header class="ds-site-header">
<div class="ds-container ds-site-header__bar">
<a class="ds-brand" href="/"><span class="ds-brand__name">SE LIGA, BRASIL</span>
<span class="ds-brand__tagline">Trajetórias públicas, fatos documentados</span></a>
<form class="ds-site-search" role="search" action="/pessoas" method="get">
<label class="ds-site-search__field"><span class="ds-visually-hidden">Buscar pessoa pelo nome</span>
<span class="ds-site-search__icon" aria-hidden="true"></span>
<input class="ds-site-search__input" name="q" type="search" value="{escape_text(query)}"
maxlength="120" placeholder="Buscar pessoa pelo nome"></label></form>
<span class="ds-site-header__menu-slot" aria-hidden="true"></span></div>
<details class="ds-site-menu"><summary>Menu</summary>
{render_site_navigation(active_section)}</details></header>'''
