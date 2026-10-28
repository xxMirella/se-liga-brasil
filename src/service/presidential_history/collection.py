"""Acquire, normalize and publish a local audited input for annual dashboard jobs."""

from crawlers.presidency.acquisition import FIRST_REPUBLIC_URL
from crawlers.presidency.parsing import parse_first_republic_chronology
from service.presidential_history.biographies import enrich_presidential_biographies
from storage.files import save_json


def collect_presidential_chronology(acquisition, output_path):
    artifact = acquisition.acquire(FIRST_REPUBLIC_URL)
    records = parse_first_republic_chronology(
        artifact.path.read_bytes(), source_url=FIRST_REPUBLIC_URL,
        sha256=artifact.sha256, fetched_at=artifact.fetched_at,
    )
    records, biographical_reviews = enrich_presidential_biographies(acquisition, records)
    payload = {
        "schema_version": "historical_executive_evidence.v1", "exercises": records,
        "coverage": "historical_chronology_partial", "year_start": 1889, "year_end": 1930,
        "limitations": ["interim_exercises_not_exhaustive", "year_precision_only",
                        "historical_political_party_affiliation_partial"],
        "canonical_person_linking": "not_attempted_source_qualified_identifiers_only",
        "biographical_reviews": biographical_reviews,
    }
    save_json(output_path, payload)
    return {"records": len(records), "output": str(output_path),
            "verified_historical_party_records": sum(
                row["political_party_status"].startswith("verified_")
                for row in records),
            "coverage": payload["coverage"], "source_url": FIRST_REPUBLIC_URL}
