"""One monthly proposition card, with distinct dated votes in a native dialog."""

from collections import OrderedDict
from hashlib import sha256

from service.public_profile_web.document_links import render_reading_links
from service.public_profile_web.security import official_url, text
from service.public_profile_web.votes import (
    RESULTS,
    render_individual_vote,
    render_item_date,
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


TYPE_LABELS = {
    "PL": "Projeto de lei", "PLP": "Projeto de lei complementar",
    "PEC": "Proposta de emenda à Constituição", "PDL": "Projeto de decreto legislativo",
    "PRL": "Parecer como relator(a)",
    "SBT": "Substitutivo (texto alternativo da relatoria)", "SBR": "Subemenda da relatoria",
    "REQ": "Requerimento", "INC": "Indicação (sugestão ao governo)", "RCP": "Pedido de CPI",
    "PLN": "Projeto de lei do Congresso Nacional", "PLV": "Projeto de lei de conversão",
    "MPV": "Medida provisória", "PRC": "Projeto de resolução",
    "RIC": "Requerimento de informação", "EMC": "Emenda na comissão",
    "EMP": "Emenda de plenário",
}
LAW_SIGLAS = frozenset({"PL", "PLP", "PEC", "PDL", "PLN", "PLV", "MPV", "PRC"})
RAPPORTEUR_SIGLAS = frozenset({"PRL", "SBT", "SBR"})
REQUEST_SIGLAS = frozenset({"REQ", "INC", "RCP", "RIC"})
REFERENCE_SIGLAS = ("PL", "PLP", "PEC", "PDL", "PRL", "SBT", "SBR", "REQ", "INC", "RCP")


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
    categories = " ".join(matter_categories(records))
    noun = "registro" if len(records) == 1 else "registros"
    count_label = f"{len(records)} {noun} neste mês"
    return f"""<article class="timeline-event monthly-proposition" data-category="{categories}">
<div class="event-body"><div class="ds-profile-item__head">
<strong class="ds-profile-item__code">{title}</strong>{render_type_label(first)}
<span class="ds-profile-item__count">{count_label}</span></div>
<p class="ds-profile-item__summary">{description}</p>
<p class="voting-dates">{render_voting_dates(records)}</p>
<div class="ds-profile-item__actions"><button type="button" commandfor="{dialog_id}"
command="show-modal">Ver histórico da matéria</button></div>
<p class="event-footer">{institution} · Cada pauta e turno mantém seu próprio voto.</p></div>
<div class="ds-profile-item__side">{render_item_date(first)}{render_source_link(records)}</div>
</article><dialog id="{dialog_id}" class="attendance-dialog voting-history-dialog"
aria-labelledby="{dialog_id}-title"><header><h2 id="{dialog_id}-title">{title}</h2>
<form method="dialog"><button autofocus aria-label="Fechar histórico de votações">Fechar</button>
</form></header><div class="attendance-dialog-content"><p>Ações disponíveis neste mês.
Autoria, tramitação e votos em emendas, requerimentos e texto principal são registros distintos.</p>
<ol>{entries}</ol></div></dialog>"""


def proposition_sigla(item):
    proposition = item.get("proposition") or {}
    kind = str(proposition.get("kind") or "").strip().upper()
    if kind in TYPE_LABELS:
        return kind
    first_word = str(proposition.get("title") or "").split(" ")[0].upper()
    return first_word if first_word in TYPE_LABELS else None


def render_type_label(item):
    sigla = proposition_sigla(item)
    if sigla is None:
        label = "Votação" if item.get("action_type") in {None, "vote"} else ""
    else:
        label = TYPE_LABELS[sigla]
    return f'<span class="ds-profile-item__type">{label}</span>' if label else ""


def matter_categories(records):
    """Categories a monthly card belongs to; only evidenced authorship counts as authored."""
    sigla = proposition_sigla(records[0])
    authorship = [r for r in records if r.get("action_type") == "authorship"]
    roles = {role for record in authorship for role in record.get("roles") or []}
    categories = []
    if authorship and roles & {"author", "coauthor"} and sigla in LAW_SIGLAS:
        categories.append("lei")
    if "rapporteur" in roles or sigla in RAPPORTEUR_SIGLAS:
        categories.append("rel")
    if authorship and roles & {"author", "coauthor"} and sigla in REQUEST_SIGLAS:
        categories.append("ped")
    if any(r.get("action_type") in {None, "vote"} for r in records):
        categories.append("votes")
    return categories


def render_source_link(records):
    for record in records:
        proposition = record.get("proposition") or {}
        source = official_url(record.get("official_url") or proposition.get("official_url"))
        if source:
            house = (record.get("institution") or {}).get("code")
            label = "Ver na Câmara" if house == "camara" else "Ver na fonte oficial"
            return (f'<a class="ds-profile-item__link" href="{text(source)}" target="_blank" '
                    f'rel="noopener noreferrer">{label} ↗</a>')
    return ""


def summarize_activity(items):
    """Count monthly cards per category with the same grouping the timeline renders."""
    from service.public_profile_web.votes import voting_month

    months = OrderedDict()
    for item in items:
        months.setdefault(voting_month(item), []).append(item)
    counts = {"todos": 0, "lei": 0, "rel": 0, "ped": 0, "votes": 0}
    siglas = set()
    for month_items in months.values():
        matters = OrderedDict()
        for item in month_items:
            matters.setdefault(proposition_group_key(item), []).append(item)
        for records in matters.values():
            counts["todos"] += 1
            for category in matter_categories(records):
                counts[category] += 1
            if proposition_sigla(records[0]):
                siglas.add(proposition_sigla(records[0]))
    return counts, siglas


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
