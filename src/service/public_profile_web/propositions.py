"""Authorship history shows official submission dates, independently of votes."""

from collections import OrderedDict

from service.public_profile_web.document_links import render_reading_links
from service.public_profile_web.security import official_url, person_path, text
from service.public_profile_web.votes import MONTHS

ROLES = {"author": "Autoria", "coauthor": "Coautoria", "rapporteur": "Relatoria"}


def render_person_propositions(profile):
    projection = profile.get("propositions") or {}
    items = projection.get("items") or []
    if not items:
        return ""
    groups = OrderedDict()
    for item in items:
        month = (item.get("occurred_on") or "")[:7] or None
        groups.setdefault(month, []).append(item)
    sections = []
    for month, records in groups.items():
        label = "Data de apresentação não informada"
        if month:
            year, number = month.split("-")
            label = f"{MONTHS[int(number)]} de {year}"
        cards = "".join(render_authorship_card(item) for item in records)
        sections.append(f'<section class="timeline-group"><h3 class="month-heading">{label}</h3>'
                        + cards + "</section>")
    limited = render_proposition_pagination(profile, projection)
    return (
        '<section aria-labelledby="person-propositions"><h2 id="person-propositions">'
        'Propostas e participação na criação</h2><p class="explanation">'
        'Apresentar uma proposta não significa que ela foi aprovada ou virou lei.</p>'
        '<div class="timeline activity-timeline">' + "".join(sections) + "</div>"
        + limited + "</section>"
    )


def render_proposition_pagination(profile, projection):
    page = projection.get("page", 1)
    links = []
    path = person_path(profile["person_id"])
    if page > 1:
        links.append(
            f'<a href="{path}?proposal_page={page - 1}#person-propositions">← Anteriores</a>'
        )
    if projection.get("truncated"):
        links.append(
            f'<a href="{path}?proposal_page={page + 1}#person-propositions">Mais propostas →</a>'
        )
    return '<nav class="pagination" aria-label="Propostas">' + " · ".join(links) + "</nav>"


def render_authorship_card(item):
    roles = " · ".join(ROLES.get(role, "Papel documentado") for role in item.get("roles", []))
    source = official_url(item.get("official_url"))
    link = (
        f'<a href="{text(source)}" target="_blank" rel="noopener noreferrer">'
        'Proposta na fonte oficial ↗</a>'
        if source else ""
    )
    occurred = item.get("occurred_on")
    year = occurred[:4] if occurred else "Sem data"
    month = MONTHS[int(occurred[5:7])][:3].upper() if occurred else "—"
    return (
        '<article class="timeline-event"><div class="event-date">'
        f'<strong>{month}</strong><span>{year}</span></div><div class="event-body">'
        f'<p class="category">{text(roles)} · {text(item.get("institution"))}</p>'
        f'<h3>{text(item.get("title"))}</h3><p>{text(item.get("summary"))}</p>'
        f'<p>Apresentação: {text(occurred, "Data não informada")}</p>'
        f'{render_reading_links(item | {"action_type": "authorship"})}{link}</div></article>'
    )
