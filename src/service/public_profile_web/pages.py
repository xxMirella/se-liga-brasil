"""Compose server-rendered pages exclusively from public service projections."""

from service.public_profile_web.activity import render_person_activity
from service.public_profile_web.asset_declarations import render_asset_declarations
from service.public_profile_web.forms import render_vote_filters
from service.public_profile_web.layout import render_layout
from service.public_profile_web.office_scopes import render_office_scopes
from service.public_profile_web.profile import render_profile_header
from service.public_profile_web.propositions import render_person_propositions
from service.public_profile_web.security import person_path, query_link, text
from service.public_profile_web.votes import render_vote_pagination


def render_tabs(path, filters, active):
    tabs = []
    for value, label in (("profile", "Perfil"), ("activity", "Atuação no cargo")):
        parameters = {"tab": value, "scope": "history"} if value == "activity" else {"tab": value}
        href = query_link(path, parameters)
        selected = ' aria-current="page" class="selected"' if value == active else ""
        tabs.append(f'<a href="{href}"{selected}>{label}</a>')
    return '<nav class="profile-tabs" aria-label="Seções do perfil">' + "".join(tabs) + "</nav>"


def render_coverage(votes):
    coverage = votes.get("coverage") or {}
    datasets = coverage.get("datasets") or {}
    history = datasets.get("history_range") == "available_published_history"
    complete = coverage.get("requested_period_state") == "verified_for_interval"
    title = (
        "Cobertura documentada para o intervalo"
        if complete
        else "Cobertura parcial ou ainda não certificada"
    )
    scope = (
        "<p>Todo o histórico publicado disponível, do mais recente ao mais antigo.</p>"
        if history
        else ""
    )
    return f"""<aside class="coverage-banner"><strong>{title}</strong>{scope}
<p>Os registros apresentados têm vínculo com esta pessoa. A ausência de registros
não comprova inatividade. O histórico completo da vida pública ainda não está
certificado.</p></aside>"""


def render_profile_overview(profile):
    return f"""<section aria-labelledby="profile-overview"><h2
id="profile-overview">Informações do perfil</h2>
<p class="profile-reference">Referência da consulta: {text(profile.get("as_of"))}.</p>
<p class="explanation">O cabeçalho apresenta os vínculos e pagamentos disponíveis.
Remuneração publicada é identificada pela competência; não equivale automaticamente ao salário
vigente.</p>
{render_asset_declarations(profile)}
{render_person_propositions(profile)}
<p><a href="#main">Voltar ao início do perfil ↑</a></p></section>"""


def render_person_profile(profile, votes, filters):
    path = person_path(profile["person_id"])
    active = "activity" if filters.get("tab") == "activity" else "profile"
    content = '<p class="breadcrumb"><a href="/pessoas">Consulta pública</a> / Perfil</p>'
    content += render_profile_header(profile) + render_tabs(path, filters, active)
    if active == "activity":
        content += (
            '<section class="activity-panel"><div class="section-head"><div>'
            '<p class="eyebrow">FEITOS E RESPONSABILIDADES</p><h2>Atuação no cargo</h2>'
            '<p>Trabalho documentado ao longo de cada exercício.</p></div></div>'
            '<div class="activity-history"><p class="eyebrow">FEITOS E VOTAÇÕES</p>'
            '<h2>Atuação ao longo do tempo</h2>'
        )
        content += render_person_activity(profile, votes, filters)
        content += render_vote_pagination(path, votes, filters)
        content += render_vote_filters(path, votes, filters)
        content += "</div>"
        content += (
            '<details class="activity-context">'
            "<summary>Sobre os registros e o cargo</summary>"
        )
        content += render_coverage(votes) + render_office_scopes(profile, votes, filters)
        content += "</details>"
        content += "</section>"
    else:
        content += render_profile_overview(profile)
    return render_layout(profile.get("display_name") or "Perfil público", content)


def render_error_page(status, message="A consulta não pôde ser concluída. Tente novamente."):
    content = (
        f"<h1>Consulta indisponível</h1><p>{text(message)}</p><p>Código "
        f'{text(status)}</p><a href="/pessoas">Voltar à busca</a>'
    )
    return render_layout("Consulta indisponível", content)
