"""Compose evidenced actions without deriving relationships from similar titles."""

from itertools import islice

from service.public_profile_web.propositions import render_proposition_pagination
from service.public_profile_web.votes import render_votes_timeline


def proposition_activity_items(item):
    proposition = {key: item.get(key) for key in (
        "id", "official_key", "kind", "number", "year", "title", "official_parent",
        "document_label"
    )}
    base = {
        "proposition": proposition,
        "institution": {"code": item.get("institution_code"), "name": item.get("institution")},
        "official_url": item.get("official_url"),
        "short_description": item.get("summary"),
    }
    records = [base | {
        "action_type": "authorship", "roles": item.get("roles") or [],
        "occurred_on": item.get("occurred_on"),
        "date_precision": item.get("date_precision", "unknown"),
        "action_id": "authorship:" + str(item.get("id") or item.get("official_key") or id(item)),
    }]
    for event in islice(item.get("events") or [], 100):
        occurred = str(event.get("occurred_at") or "")
        occurred_on = str(event.get("occurred_on") or occurred[:10]) or None
        records.append(base | {
            "action_type": "proposition_event", "event_type": event.get("event_type"),
            "occurred_on": occurred_on,
            "date_precision": "day" if occurred_on else "unknown",
            "subject": event.get("description"),
            "action_id": event.get("official_event_key"),
            "official_url": event.get("official_event_key") or item.get("official_url"),
        })
    return records


def render_person_activity(profile, votes, filters=None):
    filters = filters or {}
    records = [item | {"action_type": "vote"} for item in islice(votes.get("items") or [], 100)]
    projection = profile.get("propositions") or {}
    propositions = list(islice(projection.get("items") or [], 100))
    restricted = bool(filters.get("office_kind") or filters.get("exercise_id"))
    if not restricted:
        for item in propositions:
            records.extend(filter_activity_period(proposition_activity_items(item), votes, filters))
    records.sort(key=lambda item: item.get("occurred_on") or "", reverse=True)
    timeline = render_votes_timeline(votes | {"items": records}, maximum_items=10200)
    limited = any(item.get("events_truncated") for item in propositions)
    notice = (
        '<p>Há mais ações da matéria além do limite de 100 por proposta nesta página.</p>'
        if limited else ''
    )
    if restricted:
        notice += (
            '<p>Autoria e tramitação sem vínculo comprovado ao cargo filtrado '
            'não são exibidas.</p>'
        )
    return (
        '<section id="person-propositions"><p class="explanation">'
        'Ações da mesma matéria e do mesmo mês aparecem juntas. A tramitação da matéria '
        'não significa que cada ação foi realizada pela pessoa. Apresentar uma proposta '
        'não significa aprovação. O histórico reúne os registros disponíveis nesta página.</p>'
        + timeline + notice + render_proposition_pagination(profile, projection) + '</section>'
    )


def filter_activity_period(records, votes, filters):
    if filters.get("scope") == "history":
        return records
    period = votes.get("period") or {}
    start = filters.get("start_date") or period.get("starts_on")
    end = filters.get("end_date") or period.get("ends_on_inclusive")
    if not start or not end:
        return records
    return [record for record in records if record.get("occurred_on")
            and start <= record["occurred_on"] <= end]
