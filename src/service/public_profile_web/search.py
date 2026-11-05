"""Bounded public name search results; documents never enter the presentation."""

from collections.abc import Mapping
from itertools import islice

from service.public_profile.people_contracts import DEFAULT_PAGE_SIZE, UFS
from service.public_profile_web.brazilian_states import UF_NAMES
from service.public_profile_web.forms import render_radio_pills, render_select_element
from service.public_profile_web.layout import render_layout
from service.public_profile_web.profile import OFFICE_LABELS
from service.public_profile_web.search_results import (
    render_empty_state,
    render_next_page,
    render_result_count,
    render_search_result,
)
from service.public_profile_web.security import query_link, text

HERO_LEAD = "Identidade, vínculos e atuação disponíveis nas fontes consultadas."


def render_search_hero(parameters, title):
    query = text(parameters.get("q"), "")
    return f'''<section class="ds-people-hero"><span class="ds-eyebrow">Consulta pública</span>
<h1>{text(title)}</h1><p class="ds-people-hero__lead">{HERO_LEAD}</p>
<label class="ds-people-search"><span class="ds-visually-hidden">Buscar pelo nome</span>
<span class="ds-people-search__icon" aria-hidden="true"></span>
<input form="people-search" name="q" value="{query}" type="search" maxlength="120"
placeholder="Buscar pelo nome, ex.: Tabata, Romário"></label></section>'''


def render_uf_panel(parameters):
    uf_options = ((uf, UF_NAMES.get(uf, uf)) for uf in sorted(UFS))
    control = render_select_element(
        "uf", uf_options, parameters.get("uf"), empty_caption="Escolha um estado",
        css_class="ds-people-select ds-people-select--large", label_text="Seu estado",
    )
    return f'''<section class="ds-people-panel" aria-labelledby="people-representation">
<div class="ds-people-panel__text"><h2 id="people-representation">Quem representa você?</h2>
<p>Escolha seu estado para ver quem foi eleito por ele.</p></div>{control}</section>'''


SORT_OPTIONS = (("party", "Partido"), ("state", "Estado"))
SEARCH_ENHANCEMENT_SCRIPT = "/assets/people-search-enhance.js"


def render_sort_control(parameters):
    """Sort dropdown; the empty value is the default, name A-Z."""
    control = render_select_element(
        "sort", SORT_OPTIONS, parameters.get("sort"), empty_caption="Nome A–Z",
        css_class="ds-people-select",
    )
    return f'<label class="ds-people-field">Ordenar por{control}</label>'


def render_party_control(parameters, party_options):
    """Dropdown of existing parties; a plain text field when the list is unavailable."""
    selected = text(parameters.get("political_party"), "")
    if not party_options:
        return (
            '<label class="ds-people-field">Partido (sigla)<input class="ds-people-select" '
            f'name="political_party" value="{selected}" maxlength="40"></label>'
        )
    options = [
        (abbreviation, abbreviation if name.upper() == abbreviation else f"{abbreviation} · {name}")
        for abbreviation, name in party_options
    ]
    selected = selected.upper()
    if selected and selected not in {abbreviation for abbreviation, _ in party_options}:
        options.insert(0, (selected, selected))
    control = render_select_element(
        "political_party", options, selected,
        empty_caption="Todos os partidos", css_class="ds-people-select",
    )
    return f'<label class="ds-people-field">Partido{control}</label>'


def render_filter_row(parameters, party_options):
    pills = render_radio_pills(
        "office_kind", "Cargo atual", OFFICE_LABELS.items(), parameters.get("office_kind")
    )
    return f'''<div class="ds-people-filter-row">{pills}
{render_party_control(parameters, party_options)}{render_sort_control(parameters)}
<button class="ds-button ds-button--primary" type="submit">Filtrar pessoas</button></div>'''


def render_search_filters(parameters, party_options=()):
    return f'''<form id="people-search" class="ds-people-filters" action="/pessoas" method="get">
{render_uf_panel(parameters)}{render_filter_row(parameters, party_options)}</form>'''


def render_search_page(query, results, *, party_options=()):
    parameters = dict(query) if isinstance(query, Mapping) else {"q": query}
    search_text = parameters.get("q") or ""
    people = list(islice(results.get("items", []), 100))
    heading = search_heading(parameters)
    records = "".join(render_search_result(person) for person in people)
    count = render_result_count(len(people)) if people else ""
    if not records:
        records = render_empty_state(any(parameters.values()))
    next_link = ""
    if results.get("next_cursor"):
        url = query_link("/pessoas", {**parameters, "cursor": results["next_cursor"]})
        next_link = render_next_page(url, DEFAULT_PAGE_SIZE)
    intro = render_search_hero(parameters, heading)
    content = f"""{intro}{render_search_filters(parameters, party_options)}{count}
<ul class="ds-people-list">{records}</ul>
{next_link}"""
    return render_layout(
        heading, content, search_text, scripts=(SEARCH_ENHANCEMENT_SCRIPT,)
    )


def search_heading(parameters):
    filtered = any(parameters.get(key) for key in ("q", "uf", "office_kind", "political_party"))
    return "Resultados da busca" if filtered else "Conheça as trajetórias públicas"
