"""Select documented year-end exercise from dated official status history."""

from collections import defaultdict
from datetime import datetime


def documented_year_end_status(events, legislatures, year):
    reference = datetime(year, 12, 31, 23, 59, 59)
    candidates = []
    for legislature_id, bounds in legislatures.items():
        start = datetime.fromisoformat(bounds["dataInicio"])
        end = datetime.fromisoformat(bounds["dataFim"])
        if not start.date() <= reference.date() <= end.date():
            continue
        status = latest_unambiguous_status(events, legislature_id, start, reference)
        if status and status.get("situacao") == "Exercício":
            candidates.append(status)
    return candidates[0] if len(candidates) == 1 else None


def latest_unambiguous_status(events, legislature_id, start, reference):
    grouped = defaultdict(list)
    for event in events:
        if (event.get("idLegislatura") != legislature_id or not event.get("situacao")
                or is_pre_possession_update(event)):
            continue
        observed = datetime.fromisoformat(event["dataHora"])
        if start <= observed <= reference:
            grouped[observed].append(event)
    if not grouped:
        return None
    latest = resolve_simultaneous_summons(grouped[max(grouped)])
    signatures = {
        (row.get("situacao"), row.get("siglaPartido"), row.get("siglaUf")) for row in latest
    }
    return latest[0] if len(signatures) == 1 else None


def resolve_simultaneous_summons(events):
    """A summons is administrative when the same instant explicitly records entry.

    Preserve genuine departure/entry or party conflicts as unresolved. A summons alone
    never establishes exercise.
    """
    entries = [row for row in events if row.get("situacao") == "Exercício"
               and str(row.get("descricaoStatus", "")).startswith("Entrada - ")]
    if not entries:
        return events
    signatures = {(row.get("siglaPartido"), row.get("siglaUf")) for row in events}
    if len(signatures) != 1:
        return events
    if any(row.get("situacao") not in {"CONVOCADO", "Exercício"} for row in events):
        return events
    return entries



def is_pre_possession_update(event):
    return "em data anterior à posse" in str(event.get("descricaoStatus", "")).casefold()
