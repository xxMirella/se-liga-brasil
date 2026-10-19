"""Normalize reported dates without inventing a legal end-date boundary."""

from datetime import date

from database.political_party_verification import persist_party_evidence


def collect_affiliation_reports(resolutions) -> list:
    reports = []
    for resolution in resolutions:
        if resolution["status"] != "matched":
            continue
        subjects = resolution.get("official_subjects", [])
        reviewed = resolution.get("reviewed_crosswalk")
        if reviewed:
            subjects = subjects + [reviewed]
        for subject in subjects:
            reports.extend(normalize_subject_affiliations(subject, resolution["person_id"]))
    return reports


def normalize_subject_affiliations(subject, person_id) -> list:
    reports = []
    for affiliation in subject.get("affiliations", []):
        political_party = affiliation.get("partido") or {}
        start, end = affiliation.get("dtInicio"), affiliation.get("dtFim")
        if not start or not political_party.get("nuLegenda"):
            continue
        date.fromisoformat(start)
        if end:
            date.fromisoformat(end)
        reports.append(
            {
                "person_id": str(person_id),
                "political_party_code": str(political_party["nuLegenda"]).zfill(2),
                "starts_on": start,
                "reported_end_date": end,
                "end_boundary": "not_documented",
                "evidence_scope": "alesp_reported_affiliation",
                "source_url": next(
                    (
                        item["url"]
                        for item in subject.get("sources", [])
                        if "parlamentar-portal/detalhes/" in item["url"]
                    ),
                    None,
                ),
                "sources": [
                    {"url": item["url"], "sha256": item["sha256"]}
                    for item in subject.get("sources", [])
                ],
            }
        )
    return reports


def save_alesp_affiliation_reports(connection, source_id, source_url, resolutions) -> int:
    reports = collect_affiliation_reports(resolutions)
    persist_party_evidence(
        connection, source_id, source_url, reports, "political_party_affiliation_report"
    )
    return len(reports)
