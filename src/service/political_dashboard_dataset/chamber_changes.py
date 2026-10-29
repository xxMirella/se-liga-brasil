"""Summarize dated source events without interpreting them as a simultaneous roster."""

from collections import Counter, defaultdict


def dated_chamber_changes(histories, year, cutoff):
    dates = defaultdict(Counter)
    seen = set()
    for history in histories:
        for event in history["events"]:
            observed = event["dataHora"][:10]
            if observed[:4] != str(year) or observed > cutoff:
                continue
            description = event.get("descricaoStatus", "")
            kind = source_transition_kind(description)
            if kind == "entry" and event.get("situacao") != "Exercício":
                continue
            key = (history["official_deputy_id"], event["dataHora"], kind)
            if kind and key not in seen:
                seen.add(key)
                dates[observed][kind] += 1
    return [{"date": observed, **counts} for observed, counts in sorted(dates.items())]


def source_transition_kind(description):
    if description == "Alteração de partido":
        return "affiliation"
    if description.startswith("Entrada - "):
        return "entry"
    if description.startswith("Saída - "):
        return "exit"
    return None
