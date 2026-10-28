"""Official party attribution belongs to its documented presidential term, not all careers."""

from copy import deepcopy

from crawlers.presidency.camara_mandates import (
    REVIEWED_CAMARA_PROFILES,
    parse_camara_presidential_mandates,
)
from service.ingestion.contracts import IngestionError
from service.presidential_history.biographies import exercise_year_bounds


def apply_official_presidential_term_party(record, observation, evidence, *, abbreviation, name):
    first_year, last_year = exercise_year_bounds(record)
    if observation["year_start"] != first_year:
        return False
    if observation["year_end"] is None and record.get("ends_before"):
        return False
    if observation["political_party_abbreviation"] != abbreviation:
        raise IngestionError("CAMARA_PRESIDENTIAL_PARTY_REQUIRES_HISTORICAL_REVIEW")
    record.update(
        political_party_code="official-presidential-term:BR:" + abbreviation,
        political_party= name, political_party_abbreviation=abbreviation,
        political_party_status="verified_official_presidential_term_party",
        political_party_context="official_presidential_term_party_record",
        political_party_year_start=first_year,
        political_party_year_end=min(observation["year_end"] or last_year, last_year),
        political_party_evidence=[evidence],
        political_party_limitation="term_party_attribution_not_continuous_affiliation_proof",
    )
    record.setdefault("political_party_observations", []).append(
        observation | {"kind": "official_presidential_term_party_record", "evidence": evidence})
    return True


def enrich_official_presidential_term_parties(acquisition, exercises):
    enriched, reviews = deepcopy(exercises), []
    for archive_id, profile_id, subject, abbreviation, name in REVIEWED_CAMARA_PROFILES:
        url = "https://www.camara.leg.br/deputados/" + profile_id + "/biografia"
        artifact = acquisition.acquire(url)
        observations = parse_camara_presidential_mandates(
            artifact.path.read_bytes(), subject=subject,
        )
        matched = 0
        for record in enriched:
            if record["person_id"] != "arquivo-nacional-president:" + archive_id:
                continue
            for observation in observations:
                evidence = {"url": url, "sha256": artifact.sha256,
                            "fetched_at": artifact.fetched_at, "locator": observation["locator"],
                            "source_type": "official_external_mandate_field"}
                matched += apply_official_presidential_term_party(
                    record, observation, evidence, abbreviation=abbreviation, name=name,
                )
        reviews.append({"url": url, "matched_exercises": matched,
                        "kind": "official_presidential_term_party_record"})
    return enriched, reviews
