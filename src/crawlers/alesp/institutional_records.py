"""Normalize personally verified institutional observations without inventing exercise dates."""

from datetime import date, timedelta


def institutional_profiles(resolutions, person_ids=None):
    for resolution in resolutions:
        person_id = str(resolution["person_id"])
        if resolution["status"] != "matched" or (
            person_ids is not None and person_id not in person_ids
        ):
            continue
        for subject in resolution.get("official_subjects", []):
            sources = [
                source
                for source in subject.get("sources", [])
                if source.get("evidence_kind") == "profile"
            ]
            if not sources:
                continue
            observed_at = sources[0]["fetched_at"]
            yield {
                "personId": person_id,
                "inExercise": subject.get("is_in_office"),
                "officeKind": "state_deputy",
                "representedUf": "SP",
                "observedAt": observed_at,
                "politicalPartyCode": subject.get("political_party_code"),
                "affiliations": subject.get("affiliations", []),
                "mandates": [normalize_mandate(row) for row in subject.get("mandates", [])],
                "evidence": [{"url": s["url"], "sha256": s["sha256"]} for s in subject["sources"]],
            }


def normalize_mandate(row):
    start, end = row.get("dtInicio"), row.get("dtTermino")
    if start:
        date.fromisoformat(start)
    if end:
        end = (date.fromisoformat(end) + timedelta(days=1)).isoformat()
    return {
        "legislatureKey": str(row["idLegislatura"]),
        "termStart": start,
        "termEndExclusive": end,
        "exerciseStart": None,
        "dateScope": "legislature_period_not_individual_exercise",
    }
