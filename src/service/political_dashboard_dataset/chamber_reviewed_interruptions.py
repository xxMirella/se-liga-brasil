"""Apply reviewed explanations only to their exact archived events and UF snapshot."""

import hashlib
import json

VACANCY_KIND = "renunciation_awaiting_possession"
INTERRUPTION_KINDS = frozenset({
    "licensed_awaiting_possession", "serving_substitute_effectuated", "judicial_suspension",
})


def reviewed_snapshot_cases(cases, histories, members, uf_rows, year):
    indexed = {row["official_deputy_id"]: row["events"] for row in histories}
    deficits = {row["uf"]: row["unresolved"] for row in uf_rows}
    selected, seen = [], set()
    for case in cases:
        if case["year"] != year:
            continue
        uf = case["uf"]
        if uf in seen or deficits.get(uf) != 1:
            raise ValueError("CHAMBER_REVIEWED_CASE_NO_LONGER_MATCHES_DEFICIT")
        validate_reviewed_snapshot(case, indexed, members)
        selected.append(public_reviewed_case(case))
        seen.add(uf)
    return selected


def validate_reviewed_snapshot(case, indexed, members):
    identifiers = sorted(row["source_person_id"] for row in members if row["uf"] == case["uf"])
    digest = hashlib.sha256(json.dumps(identifiers, separators=(",", ":")).encode()).hexdigest()
    if digest != case["uf_member_ids_sha256"]:
        raise ValueError("CHAMBER_REVIEWED_UF_MEMBERS_CHANGED")
    if case["kind"] not in INTERRUPTION_KINDS | {VACANCY_KIND}:
        raise ValueError("CHAMBER_REVIEWED_CASE_KIND_UNKNOWN")
    for expected in case["events"]:
        if expected["signature"] not in indexed.get(expected["source_person_id"], []):
            raise ValueError("CHAMBER_REVIEWED_EVENT_CHANGED")


def public_reviewed_case(case):
    return {"uf": case["uf"], "reference_on": f"{case['year']}-12-31",
            "kind": case["kind"], "detail": case["detail"],
            "source_urls": sorted({row["source"]["url"] for row in case["evidence_assertions"]}),
            "evidence_sha256": sorted({row["source"]["sha256"]
                                       for row in case["evidence_assertions"]}),
            "source_person_ids": sorted({row["source_person_id"] for row in case["events"]}),
            "review_version": "chamber_year_end_cases.20261102.v1"}


def apply_reviewed_cases(cases, vacancies, uf_rows):
    interruptions = []
    rows = {row["uf"]: dict(row) for row in uf_rows}
    for case in cases:
        row = rows[case["uf"]]
        row["unresolved"] -= 1
        if case["kind"] == VACANCY_KIND:
            vacancies.append(case)
            row["documented_vacancies"] += 1
        else:
            interruptions.append(case)
            row["documented_exercise_interruptions"] = 1
    return interruptions, list(rows.values())
