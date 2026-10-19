"""A changed observation triggers verification; it does not establish legal membership."""

from bisect import bisect_right
from calendar import monthrange
from datetime import date


def index_affiliation_reports(reports) -> dict:
    indexed = {}
    for report in reports:
        if report.get("starts_on"):
            key = (str(report["person_id"]), str(report["political_party_code"]))
            indexed.setdefault(key, []).append((report["starts_on"], report["source_record_id"]))
    for entries in indexed.values():
        entries.sort()
    return indexed


def verify_monthly_political_parties(observations, reports) -> list:
    history = index_affiliation_reports(reports)
    ordered = sorted(observations, key=lambda row: (str(row["person_id"]), row["competence"]))
    previous = {}
    results = []
    for observation in ordered:
        person_id = str(observation["person_id"])
        prior = previous.get(person_id)
        result = evaluate_party_observation(prior, observation, history)
        results.append(observation | result)
        previous[person_id] = observation
    return results


def evaluate_party_observation(prior, current, history) -> dict:
    if not prior:
        return {"status": "initial_observation", "evidence_source_record_ids": []}
    if prior["political_party_code"] == current["political_party_code"]:
        return {"status": "unchanged_observation", "evidence_source_record_ids": []}
    start = prior["competence"]
    month = date.fromisoformat(current["competence"])
    end = month.replace(day=monthrange(month.year, month.month)[1]).isoformat()
    key = (str(current["person_id"]), str(current["political_party_code"]))
    entries = history.get(key, [])
    position = bisect_right(entries, (end, float("inf"))) - 1
    confirmed = position >= 0 and start < entries[position][0] <= end
    return {
        "status": "reported_change_confirmed" if confirmed else "change_requires_verification",
        "previous_political_party_code": prior["political_party_code"],
        "verification_from": start,
        "verification_through": end,
        "evidence_source_record_ids": [entries[position][1]] if confirmed else [],
        "previous_observation_source_record_id": prior["source_record_id"],
    }
