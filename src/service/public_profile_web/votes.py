"""One bounded vote page grouped by evidenced month, without judging performance."""

from collections import OrderedDict
from datetime import date
from itertools import islice

from service.public_profile_web.security import query_link, text

MONTHS = (
    "",
    "Janeiro",
    "Fevereiro",
    "Março",
    "Abril",
    "Maio",
    "Junho",
    "Julho",
    "Agosto",
    "Setembro",
    "Outubro",
    "Novembro",
    "Dezembro",
)
CHOICES = {
    "yes": "Sim · a favor do objeto votado",
    "no": "Não · contra o objeto votado",
    "abstention": "Abstenção",
    "obstruction": "Obstrução",
}
PARTICIPATION = {
    "voted": "Voto individual registrado",
    "presiding": "Presidiu a votação",
    "absent": "Ausência registrada",
    "excused": "Ausência justificada registrada",
    "not_recorded": "Sem voto individual registrado",
    "parliamentary_activity": "Atividade parlamentar registrada",
    "unknown": "Participação não disponível",
}
RESULTS = {"approved": "Aprovado", "rejected": "Rejeitado", "unknown": "Não disponível"}


def voting_month(item):
    occurred = item.get("occurred_on")
    if item.get("date_precision") not in {"day", "month", "instant"} or not occurred:
        return None
    try:
        parsed = date.fromisoformat(str(occurred))
        return parsed.strftime("%Y-%m")
    except ValueError:
        return None


def render_vote_date(item):
    value = item.get("occurred_on")
    if item.get("date_precision") == "month":
        return text(voting_month(item), "Mês não confirmado")
    if item.get("date_precision") in {"day", "instant"}:
        return text(value, "Data não disponível")
    return "Data completa não confirmada"


def render_individual_vote(item):
    individual = item.get("individual") or {}
    status = individual.get("participation_status", "unknown")
    choice = individual.get("choice") if status == "voted" else None
    choice_label = CHOICES.get(choice, "Voto individual não disponível")
    status_label = PARTICIPATION.get(status, PARTICIPATION["unknown"])
    return (
        f"<div><dt>Participação</dt><dd>{status_label}</dd></div><div><dt>Voto da "
        f"pessoa</dt><dd><span class=\"vote-choice {text(choice, 'unknown')}\">"
        f"{choice_label}</span></dd></div>"
    )


def render_event_date(item):
    month = voting_month(item)
    if month is None:
        return '<div class="event-date"><strong>—</strong><span>Sem data</span></div>'
    year, number = month.split("-")
    month_label = MONTHS[int(number)][:3].upper()
    return (
        f'<div class="event-date"><time datetime="{text(item.get("occurred_on"))}">'
        f"<strong>{month_label}</strong><span>{year}</span></time></div>"
    )


def render_month_group(month, items):
    from service.public_profile_web.vote_groups import render_monthly_vote_cards

    if month is None:
        label = "Sem mês de votação confirmado"
    else:
        year, number = month.split("-")
        label = f"{MONTHS[int(number)]} de {year}"
    cards = render_monthly_vote_cards(month, items)
    heading_id = "timeline-month-" + (month or "unknown")
    return (
        f'<section class="timeline-group" aria-labelledby="{heading_id}">'
        f'<h2 class="month-heading" id="{heading_id}">{label}</h2>{cards}</section>'
    )


def render_votes_timeline(votes, *, maximum_items=100):
    items = list(islice(votes.get("items", []), maximum_items))
    if not items:
        if (votes.get("coverage", {}).get("datasets") or {}).get("scan_budget_reached"):
            return (
                '<div class="empty-state">Nenhum voto vinculado nesta parte do histórico. '
                "Continue em próximas votações para consultar os períodos anteriores.</div>"
            )
        return (
            '<div class="empty-state"><strong>Nenhum voto vinculado neste '
            "recorte.</strong><p>Ausência de registros não comprova ausência, "
            "voto contrário ou inatividade.</p></div>"
        )
    groups = OrderedDict()
    for item in items:
        groups.setdefault(voting_month(item), []).append(item)
    dated = "".join(
        render_month_group(month, records) for month, records in groups.items() if month
    )
    undated = render_month_group(None, groups[None]) if None in groups else ""
    return '<div class="timeline activity-timeline">' + dated + undated + "</div>"


def render_vote_pagination(path, votes, filters):
    cursor = votes.get("next_cursor")
    if not cursor:
        return ""
    parameters = {**filters, "cursor": cursor, "tab": "activity"}
    href = query_link(path, parameters)
    return (
        f'<nav class="pagination" aria-label="Paginação da atuação"><a '
        f'href="{href}">Próximas votações →</a></nav>'
    )
