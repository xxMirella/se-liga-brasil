"""One monthly proposition card, with distinct dated votes in a native dialog."""

from collections import OrderedDict
from hashlib import sha256

from service.public_profile_web.document_links import render_reading_links
from service.public_profile_web.security import official_url, text
from service.public_profile_web.votes import (
    RESULTS,
    render_event_date,
    render_individual_vote,
    render_vote_date,
)

EVENT_LABELS = {
    "official_proceeding": "Tramitação oficial",
    "vote_declaration": "Declaração de voto",
    "speech": "Discurso",
    "voting_procedure": "Encaminhamento ou procedimento",
    "legislative_comment": "Comentário legislativo",
    "revision": "Revisão",
    "amendment": "Emenda documentada",
    "status_change": "Alteração de situação",
}


def proposition_group_key(item):
    proposition = item.get("proposition") or {}
    institution = item.get("institution") or {}
    parent = proposition.get("official_parent") or {}
    if parent and parent.get("institution_code") == institution.get("code"):
        proposition = parent
    identity = numbered_matter_identity(proposition)
    identity = (
        identity or proposition.get("official_key")
        or official_url(proposition.get("official_url")) or proposition.get("id")
    )
    if not identity:
        identity = item.get("action_id") or item.get("voting_id") or id(item)
    return institution.get("code") or institution.get("name"), str(identity)


def numbered_matter_identity(proposition):
    year = proposition.get("year")
    if (proposition.get("kind") and proposition.get("number")
            and type(year) is int and 1800 <= year <= 2200):
        return tuple(str(proposition[key]) for key in ("kind", "number", "year"))
    return None


def render_monthly_vote_cards(month, items):
    groups = OrderedDict()
    for item in items:
        groups.setdefault(proposition_group_key(item), []).append(item)
    return "".join(
        render_monthly_proposition(month, key, records) for key, records in groups.items()
    )


def render_monthly_proposition(month, key, records):
    first = records[0]
    proposition = first.get("proposition") or {}
    dialog_id = "voting-history-" + sha256(repr((month, key)).encode()).hexdigest()[:16]
    title = text(activity_document_title(first), "Matéria sem identificação disponível")
    description = text(first.get("short_description") or proposition.get("short_description"))
    description_kind = first.get("description_kind") or proposition.get("description_kind")
    if description_kind in {"official_text", "official_excerpt"}:
        description = "Ementa oficial: " + description
    if description_kind == "official_excerpt":
        description += " <small>Trecho da ementa oficial.</small>"
    entries = "".join(render_activity_history_entry(record) for record in records)
    institution = text((first.get("institution") or {}).get("name"))
    mixed = any(r.get("action_type") not in {None, "vote"} for r in records)
    category = "MATÉRIA E AÇÕES" if mixed else "VOTAÇÕES"
    return f"""<article class="timeline-event monthly-proposition">{render_event_date(first)}
<div class="event-body"><div class="event-top"><span class="category">{category}</span>
<span class="source-state">{len(records)} registros neste mês</span></div>
<h3>{title}</h3><p>{description}</p><p class="voting-dates">{render_voting_dates(records)}</p>
<button commandfor="{dialog_id}" command="show-modal">Ver histórico da matéria</button>
<p class="event-footer">{institution} · Cada pauta e turno mantém seu próprio voto.</p></div>
</article><dialog id="{dialog_id}" class="attendance-dialog voting-history-dialog"
aria-labelledby="{dialog_id}-title"><header><h2 id="{dialog_id}-title">{title}</h2>
<form method="dialog"><button autofocus aria-label="Fechar histórico de votações">Fechar</button>
</form></header><div class="attendance-dialog-content"><p>Ações disponíveis neste mês.
Autoria, tramitação e votos em emendas, requerimentos e texto principal são registros distintos.</p>
<ol>{entries}</ol></div></dialog>"""


def render_voting_dates(records):
    labels = {}
    for record in records:
        label = render_vote_date(record)
        round_number = record.get("round_number")
        if record.get("action_type") not in {None, "vote"}:
            labels[label] = None
            continue
        label += (
            f" · {text(round_number)}º turno"
            if round_number is not None else " · Turno não informado"
        )
        labels[label] = None
    return "Datas e turnos registrados: " + "; ".join(labels)


def render_voting_history_entry(item):
    source = official_url(item.get("official_url"))
    link = (
        f'<a href="{text(source)}" target="_blank" rel="noopener noreferrer">'
        'Ver votação na fonte oficial ↗</a>'
        if source else ""
    )
    result = RESULTS.get(item.get("collective_result"), "Resultado não disponível")
    return (
        '<li class="voting-history-entry"><dl class="vote-facts">'
        f'<div><dt>Data da votação</dt><dd>{render_vote_date(item)}</dd></div>'
        f'<div><dt>Pauta / objeto votado</dt><dd>{text(item.get("subject"))}</dd></div>'
        + render_individual_vote(item)
        + f'<div><dt>Turno</dt><dd>{text(item.get("round_number"), "Não informado")}</dd></div>'
        + f'<div><dt>Resultado coletivo</dt><dd>{result}</dd></div></dl>'
        + f'{render_reading_links(item)}{link}</li>'
    )


def render_activity_history_entry(item):
    if item.get("action_type") in {None, "vote"}:
        return render_voting_history_entry(item)
    from service.public_profile_web.propositions import ROLES

    if item["action_type"] == "authorship":
        action = " · ".join(ROLES.get(role, "Papel documentado") for role in item.get("roles", []))
        subject = "Participação documentada na proposta: " + (action or "papel documentado")
    else:
        action = EVENT_LABELS.get(item.get("event_type"), "Registro oficial")
        if item["action_type"] != "historical_activity":
            action = "Tramitação da matéria · " + action
        subject = item.get("subject")
    date_label = (
        "Data de apresentação da matéria" if item["action_type"] == "authorship" else "Data"
    )
    source = official_url(item.get("official_url"))
    link = (
        f'<a href="{text(source)}" target="_blank" rel="noopener noreferrer">'
        'Detalhes na fonte oficial ↗</a>'
        if source else ""
    )
    return (
        '<li class="voting-history-entry"><dl class="vote-facts">'
        f'<div><dt>Ação documentada</dt><dd>{text(action)}</dd></div>'
        f'<div><dt>Documento</dt><dd>{text(activity_document_title(item))}</dd></div>'
        f'<div><dt>{date_label}'
        f'</dt><dd>{render_vote_date(item)}</dd></div>'
        f'<div><dt>Descrição</dt><dd>{text(subject)}</dd></div></dl>{render_reading_links(item)}{link}</li>'
    )


def activity_document_title(item):
    proposition = item.get("proposition") or {}
    parent = proposition.get("official_parent") or {}
    title = proposition.get("title")
    if parent and parent.get("institution_code") == (item.get("institution") or {}).get("code"):
        suffix = parent.get("title") or proposition.get("document_label")
    else:
        suffix = proposition.get("document_label")
    return f"{title} — {suffix}" if title and suffix else title or suffix
