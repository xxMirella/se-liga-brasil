"""One monthly proposition card, with distinct dated votes in a native dialog."""

from collections import OrderedDict
from hashlib import sha256

from service.public_profile_web.security import official_url, text
from service.public_profile_web.votes import (
    RESULTS,
    render_event_date,
    render_individual_vote,
    render_vote_date,
)


def proposition_group_key(item):
    proposition = item.get("proposition") or {}
    institution = item.get("institution") or {}
    identity = proposition.get("id") or proposition.get("official_key")
    if not identity and proposition.get("kind") and proposition.get("number"):
        identity = (proposition["kind"], proposition["number"], proposition.get("year"))
    if not identity:
        identity = proposition.get("title") or item.get("voting_id") or id(item)
    return institution.get("code") or institution.get("name"), str(identity)


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
    title = text(proposition.get("title"), "Matéria sem identificação disponível")
    description = text(first.get("short_description") or proposition.get("short_description"))
    if (first.get("description_kind") or proposition.get("description_kind")) == "official_excerpt":
        description += " <small>Trecho da ementa oficial.</small>"
    entries = "".join(render_voting_history_entry(record) for record in records)
    institution = text((first.get("institution") or {}).get("name"))
    return f"""<article class="timeline-event monthly-proposition">{render_event_date(first)}
<div class="event-body"><div class="event-top"><span class="category">VOTAÇÕES</span>
<span class="source-state">{len(records)} registros neste mês</span></div>
<h3>{title}</h3><p>{description}</p>
<button commandfor="{dialog_id}" command="show-modal">Ver histórico de votações</button>
<p class="event-footer">{institution} · Cada pauta e turno mantém seu próprio voto.</p></div>
</article><dialog id="{dialog_id}" class="attendance-dialog voting-history-dialog"
aria-labelledby="{dialog_id}-title"><header><h2 id="{dialog_id}-title">{title}</h2>
<form method="dialog"><button autofocus aria-label="Fechar histórico de votações">Fechar</button>
</form></header><div class="attendance-dialog-content"><p>Votações disponíveis neste mês.
Votos em emendas, requerimentos e texto principal são registros distintos.</p>
<ol>{entries}</ol></div></dialog>"""


def render_voting_history_entry(item):
    source = official_url(item.get("official_url"))
    link = f'<a href="{text(source)}">Detalhes na fonte oficial ↗</a>' if source else ""
    result = RESULTS.get(item.get("collective_result"), "Resultado não disponível")
    return (
        '<li class="voting-history-entry"><dl class="vote-facts">'
        f'<div><dt>Data da votação</dt><dd>{render_vote_date(item)}</dd></div>'
        f'<div><dt>Pauta / objeto votado</dt><dd>{text(item.get("subject"))}</dd></div>'
        + render_individual_vote(item)
        + f'<div><dt>Turno</dt><dd>{text(item.get("round_number"), "Não informado")}</dd></div>'
        + f'<div><dt>Resultado coletivo</dt><dd>{result}</dd></div></dl>{link}</li>'
    )
