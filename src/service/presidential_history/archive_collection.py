"""Collect the linked national gallery, rejecting malformed periods instead of inventing them."""

from datetime import datetime
from zoneinfo import ZoneInfo

from crawlers.presidency.archive_parsing import (
    ARCHIVE_CATALOG_URL,
    discover_archive_biographies,
    parse_archive_exercises,
)
from crawlers.presidency.reviewed_transcriptions import reviewed_party_transcriptions
from service.ingestion.contracts import IngestionError
from service.presidential_history.biographies import enrich_presidential_biographies
from service.presidential_history.contemporary_observations import (
    enrich_current_presidential_observation,
)
from service.presidential_history.exercise_capacity import enrich_documented_exercise_capacity
from service.presidential_history.government_classification import (
    enrich_documented_government_classifications,
)
from service.presidential_history.government_context import enrich_documented_government_context
from service.presidential_history.official_term_parties import (
    enrich_official_presidential_term_parties,
)
from service.presidential_history.party_collection import collect_presidential_party_periods
from service.presidential_history.reviewed_exercises import apply_reviewed_exercise_corrections
from storage.files import save_json


def collect_archive_biography(acquisition, url, observed_on):
    artifact = acquisition.acquire(url)
    records = parse_archive_exercises(artifact.path.read_bytes(), artifact, observed_on=observed_on)
    review = {
        "url": url, "sha256": artifact.sha256, "fetched_at": artifact.fetched_at,
        "exercise_count": len(records),
        "status": "documented_periods" if records else "no_documented_exercise_period",
    }
    return records, review


def collect_national_presidential_archive(acquisition, output_path, *, observed_on=None):
    observed_on = observed_on or datetime.now(ZoneInfo("America/Belem")).date()
    catalog = acquisition.acquire(ARCHIVE_CATALOG_URL)
    pages = discover_archive_biographies(catalog.path.read_bytes())
    exercises, source_reviews = [], []
    for url, _ in pages:
        try:
            records, review = collect_archive_biography(acquisition, url, observed_on)
            exercises.extend(records)
            source_reviews.append(review)
        except IngestionError as error:
            source_reviews.append({"url": url, "status": "rejected", "reason": error.code})
    exercises, corrections = apply_reviewed_exercise_corrections(
        acquisition, exercises, observed_on=observed_on,
    )
    exercises = enrich_documented_exercise_capacity(acquisition, exercises)
    exercises = enrich_documented_government_context(
        acquisition, exercises, reviewed_party_transcriptions(),
    )
    exercises, biographical_reviews = enrich_presidential_biographies(acquisition, exercises)
    exercises, government_classification = enrich_documented_government_classifications(
        acquisition, exercises,
    )
    payload = archive_evidence_payload(exercises, source_reviews, corrections, biographical_reviews)
    payload["government_classification_evidence"] = government_classification
    payload["exercises"], payload["official_term_party_reviews"] = (
        enrich_official_presidential_term_parties(acquisition, payload["exercises"])
    )
    payload["exercises"], payload["contemporary_official_observation"] = (
        enrich_current_presidential_observation(acquisition, payload["exercises"])
    )
    payload["exercises"] = collect_presidential_party_periods(
        acquisition, payload["exercises"], reviewed_party_transcriptions(),
    )
    save_json(output_path, payload)
    return {"records": len(exercises), "people_or_juntas": len({row["person_id"]
            for row in exercises}), "catalog_biographies": len(pages),
            "year_start": payload["year_start"], "year_end": payload["year_end"],
            "verified_historical_party_records": sum(row["political_party_status"].startswith(
                "verified_") for row in payload["exercises"]), "output": str(output_path)}


def archive_evidence_payload(exercises, source_reviews, corrections, biographical_reviews):
    return {
        "schema_version": "historical_executive_evidence.v1",
        "exercises": sorted(exercises, key=lambda row: (row["starts_on"], row["person_id"])),
        "year_start": min(int(row["starts_on"][:4]) for row in exercises),
        "year_end": max(int(row["observed_through"][:4]) for row in exercises),
        "coverage": "historical_chronology_partial",
        "limitations": ["temporary_travel_substitutions_not_exhaustive",
                        "historical_political_party_affiliation_partial",
                        "source_boundary_discrepancies_preserved_not_imputed"],
        "canonical_person_linking": "not_attempted_source_qualified_identifiers_only",
        "catalog_url": ARCHIVE_CATALOG_URL, "source_reviews": source_reviews,
        "exercise_corrections": corrections, "biographical_reviews": biographical_reviews,
    }
