"""Bounded public name search results; documents never enter the presentation."""

from collections.abc import Mapping
from itertools import islice

from service.public_profile.people_contracts import UFS
from service.public_profile_web.forms import render_select
from service.public_profile_web.layout import render_layout
from service.public_profile_web.profile import OFFICE_LABELS
from service.public_profile_web.security import person_path, query_link, text


def render_search_result(person):
    path = person_path(person["person_id"])
    name = text(person.get("display_name"))
    office = person.get("current_office") or {}
    label = office.get("label") if isinstance(office, dict) else office
    office_label = f"<p>{text(label)}</p>" if label else ""
    return f'''<li class="search-result"><h2><a href="{path}" title="{name}">{name}</a></h2>
{office_label}<a href="{path}">Consultar perfil →</a></li>'''


def render_search_filters(parameters):
    uf_options = ((uf, uf) for uf in sorted(UFS))
    uf_control = render_select("uf", "UF do exercício atual", uf_options, parameters.get("uf"))
    office_control = render_select(
        "office_kind", "Cargo atual", OFFICE_LABELS.items(), parameters.get("office_kind")
    )
    selected_limit = parameters.get("limit", "6")
    page_sizes = sorted({6, 12, 24, int(selected_limit)})
    page_size_control = render_select(
        "limit", "Pessoas por página", ((str(size), str(size)) for size in page_sizes),
        selected_limit,
    )
    query = text(parameters.get("q"), "")
    political_party = text(parameters.get("political_party"), "")
    return f'''<div class="people-filters">
<form action="/pessoas" method="get" class="activity-controls">
<label>Nome<input name="q" value="{query}" type="search" maxlength="120"></label>
{uf_control}{office_control}
<label>Partido (sigla)<input name="political_party" value="{political_party}"
maxlength="40"></label>{page_size_control}<button type="submit">Filtrar pessoas</button></form>
</div>'''


def render_search_page(query, results):
    parameters = dict(query) if isinstance(query, Mapping) else {"q": query}
    search_text = parameters.get("q") or ""
    people = list(islice(results.get("items", []), 100))
    heading = search_heading(parameters)
    records = "".join(render_search_result(person) for person in people)
    if not records:
        message = (
            "Nenhuma pessoa encontrada para estes filtros."
            if any(parameters.values())
            else "Busque uma pessoa pelo nome."
        )
        records = f'<li class="empty-state">{message}</li>'
    next_link = ""
    if results.get("next_cursor"):
        url = query_link("/pessoas", {**parameters, "cursor": results["next_cursor"]})
        next_link = (
            '<nav class="pagination" aria-label="Paginação"><a '
            f'href="{url}">Próximos resultados →</a></nav>'
        )
    content = f"""<p class="eyebrow">CONSULTA PÚBLICA</p><h1>{heading}</h1>
<p class="explanation">Identidade, vínculos e atuação disponíveis nas fontes consultadas.</p>
{render_search_filters(parameters)}<ul class="search-results">{records}</ul>{next_link}"""
    return render_layout(heading, content, search_text)


def render_search_shell(parameters):
    """No database query until the browser supplies its bounded visible page size."""
    heading = search_heading(parameters)
    fallback = query_link("/pessoas", {**parameters, "limit": "6"})
    content = f'''<p class="eyebrow">CONSULTA PÚBLICA</p><h1>{heading}</h1>
<p class="explanation">Identidade, vínculos e atuação disponíveis nas fontes consultadas.</p>
{render_search_filters(parameters)}
<ul class="search-results" data-viewport-page aria-label="Preparando resultados">
<li class="search-result" aria-hidden="true"><h2>Carregando pessoas…</h2>
<span>Consultar perfil →</span></li></ul>
<p><a href="{fallback}">Carregar 6 pessoas por página</a></p>
<script src="/assets/people-viewport.js" defer></script>'''
    return render_layout("Consulta de pessoas", content, parameters.get("q", ""))


def search_heading(parameters):
    filtered = any(parameters.get(key) for key in ("q", "uf", "office_kind", "political_party"))
    return "Resultados da busca" if filtered else "Conheça as trajetórias públicas"
