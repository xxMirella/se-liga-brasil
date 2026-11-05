"""Section "Atuação no cargo" of the person profile (reference: Perfil v2, #atuacao)."""

from html import escape

from service.public_profile_web.activity import build_person_activity
from service.public_profile_web.forms import render_vote_filters
from service.public_profile_web.office_scopes import render_office_scopes
from service.public_profile_web.security import person_path
from service.public_profile_web.vote_groups import REFERENCE_SIGLAS, TYPE_LABELS
from service.public_profile_web.votes import render_vote_pagination
from web_components import render_disclosure, render_notice

ACTIVITY_SCRIPT = "/assets/profile-activity.js"
PAGE_SIZE = 8
LEAD = (
    "Apresentar uma proposta não significa que ela foi aprovada ou virou lei. "
    "Escolha um tipo para filtrar."
)
CATEGORIES = (
    ("todos", "Tudo", "Todos os registros desta página"),
    ("lei", "Propostas de lei",
     "Projetos de lei, PEC e decretos legislativos de autoria ou coautoria"),
    ("rel", "Trabalho como relator(a)",
     "Pareceres e textos alternativos sobre propostas de outras pessoas"),
    ("ped", "Pedidos e requerimentos", "Audiências, urgências, CPIs e sugestões ao governo"),
    ("votes", "Votações", "Participação registrada em votações da casa legislativa"),
)


def render_category_cards(counts):
    cards = "".join(
        f'<div class="ds-profile-category" data-category="{key}">'
        f'<strong>{counts.get(key, 0)}</strong><span class="ds-profile-category__label">'
        f'{escape(label)}</span><span class="ds-profile-category__hint">{escape(hint)}</span>'
        "</div>"
        for key, label, hint in CATEGORIES if key != "votes" or counts.get(key)
    )
    return f'<div class="ds-profile-categories">{cards}</div>'


def render_search_control():
    return (
        '<label class="ds-profile-search" hidden><span class="ds-profile-sr-only">'
        'Buscar nas propostas</span><span class="ds-profile-search__icon" aria-hidden="true">'
        '</span><input type="search" autocomplete="off" '
        'placeholder="Buscar por tema, ex.: Maria da Penha"></label>'
    )


def render_acronym_glossary(siglas):
    ordered = list(REFERENCE_SIGLAS) + sorted(siglas - set(REFERENCE_SIGLAS))
    rows = "".join(
        f"<dt>{sigla}</dt><dd>{escape(TYPE_LABELS[sigla])}</dd>"
        for sigla in ordered if sigla in TYPE_LABELS
    )
    return (
        '<details class="ds-profile-glossary"><summary>O que significam as siglas</summary>'
        f"<dl>{rows}</dl></details>"
    )


def render_coverage_notice(votes):
    coverage = votes.get("coverage") or {}
    datasets = coverage.get("datasets") or {}
    history = datasets.get("history_range") == "available_published_history"
    complete = coverage.get("requested_period_state") == "verified_for_interval"
    title = (
        "Cobertura documentada para o intervalo"
        if complete else "Cobertura parcial ou ainda não certificada"
    )
    scope = (
        "<p>Todo o histórico publicado disponível, do mais recente ao mais antigo.</p>"
        if history else ""
    )
    body = f"""<strong>{title}</strong>{scope}
<p>Os registros apresentados têm vínculo com esta pessoa. A ausência de registros
não comprova inatividade. O histórico completo da vida pública ainda não está
certificado.</p>"""
    return f'<aside class="coverage-banner">{render_notice(body)}</aside>'


def render_activity_section(profile, votes, filters, path=None):
    """Full `<section id="atuacao">`: category counts, searchable list, filters, coverage."""
    path = path or person_path(profile["person_id"])
    show_more = (
        '<div class="ds-profile-more ds-profile-show-more" hidden>'
        f'<button type="button">Mostrar mais {PAGE_SIZE}</button></div>'
    )
    feed, counts, siglas = build_person_activity(profile, votes, filters, show_more)
    context = render_coverage_notice(votes) + render_office_scopes(profile, votes, filters)
    return (
        f'<section id="atuacao" class="ds-profile-activity" data-screen-label="Atuação" '
        f'data-page-size="{PAGE_SIZE}" aria-labelledby="atuacao-title">'
        '<h2 class="ds-profile-activity__title" id="atuacao-title">Atuação no cargo</h2>'
        f'<p class="ds-profile-activity__lead">{LEAD}</p>'
        + render_category_cards(counts) + render_search_control()
        + f'<span class="ds-profile-status" role="status">{counts["todos"]} registros</span>'
        + feed
        + render_vote_pagination(path, votes, filters)
        + render_vote_filters(path, votes, filters)
        + render_acronym_glossary(siglas)
        + render_disclosure("Sobre os registros e o cargo", context)
        + "</section>"
    )
