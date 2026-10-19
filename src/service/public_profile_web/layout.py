"""Shared HTML document and local stylesheet, without executable client code."""

from pathlib import Path

from service.public_profile_web.security import text


def public_stylesheet():
    return (Path(__file__).parent / "assets" / "public-profile.css").read_text(encoding="utf-8")


def render_public_navigation(active):
    links = []
    for key, label, url in (
        ("people", "Consulta de pessoas", "/pessoas"),
        ("guide", "Entenda os cargos", "/como-funciona"),
    ):
        selected = ' class="selected" aria-current="page"' if active == key else ""
        links.append(f'<a href="{url}"{selected}>{label}</a>')
    return '<nav class="profile-tabs" aria-label="Seções do portal">' + "".join(links) + "</nav>"


def render_layout(title, content, query="", *, extra_stylesheet=None, active_section="people"):
    extra_style = (
        f'<link rel="stylesheet" href="{text(extra_stylesheet)}">' if extra_stylesheet else ""
    )
    return f'''<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{text(title)} · Se Liga Brasil</title>
<link rel="stylesheet" href="/assets/public-profile.css">{extra_style}</head>
<body><a class="skip-link" href="#main">Ir para o conteúdo</a>
<header class="topbar"><a class="brand" href="/pessoas">SE LIGA <strong>BRASIL</strong>
<span>Trajetórias públicas, fatos documentados</span></a>
<form class="search" action="/pessoas" method="get">
<label for="public-search">Buscar pessoa pelo nome</label>
<div class="search-row"><input id="public-search" name="q" type="search"
value="{text(query, "")}" maxlength="120" placeholder="Buscar pessoa pelo nome">
<button type="submit">Buscar</button></div></form>
<div class="header-navigation">{render_public_navigation(active_section)}</div></header>
<main class="workspace" id="main">{content}</main>
<footer>Se Liga Brasil <span>Consulta pública · Dados oficiais com cobertura
explicitada</span></footer>
</body></html>'''
