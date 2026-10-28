"""Enrich reviewed chronological records without inferring undocumented historical affiliations."""

from copy import deepcopy
from datetime import date, timedelta

from crawlers.presidency.parsing import extract_chronology_text
from crawlers.presidency.reviewed_biographies import REVIEWED_BIOGRAPHIES
from service.ingestion.contracts import IngestionError


def reviewed_biographical_observation(payload, claim, artifact):
    text = " ".join(extract_chronology_text(payload).split())
    if claim["subject"] not in text or claim["locator"] not in text:
        raise IngestionError("PRESIDENTIAL_BIOGRAPHY_CLAIM_CHANGED")
    return {
        key: value for key, value in claim.items()
        if key not in {"record_id", "url", "subject", "locator", "display_name",
                       "archive_article_id"}
    } | {"evidence": {"url": claim["url"], "sha256": artifact.sha256,
                      "fetched_at": artifact.fetched_at, "locator": claim["locator"]}}


def apply_biographical_observation(record, observation):
    record.setdefault("political_party_observations", []).append(observation)
    if observation["kind"] not in {"party_leadership", "dated_office_political_party"}:
        return
    start_year, end_year = exercise_year_bounds(record)
    earliest_full_year = observation["year_start"] + 1
    latest_full_year = observation["year_end"] - 1
    if latest_full_year < start_year or earliest_full_year > end_year:
        return
    for field in ("political_party_code", "political_party", "political_party_abbreviation"):
        record[field] = observation[field]
    record["political_party_status"] = "verified_historical_documented_interval"
    record["political_party_year_start"] = earliest_full_year
    record["political_party_year_end"] = latest_full_year
    record["political_party_evidence"] = [observation["evidence"]]


def enrich_presidential_biographies(acquisition, records):
    enriched = deepcopy(records)
    indexed = {}
    for record in enriched:
        indexed.setdefault(record["person_id"], []).append(record)
    reviews = []
    for claim in REVIEWED_BIOGRAPHIES:
        record_id = "arquivo-nacional-president:" + claim.get("archive_article_id", "")
        matched_records = indexed.get(claim["record_id"]) or indexed.get(record_id)
        if not matched_records:
            continue
        try:
            artifact = acquisition.acquire(claim["url"])
            observation = reviewed_biographical_observation(
                artifact.path.read_bytes(), claim, artifact,
            )
            for record in matched_records:
                apply_biographical_observation(record, observation)
                apply_reviewed_display_name(record, claim, observation["evidence"])
            reviews.append({"url": claim["url"], "status": "verified", "kind": claim["kind"]})
        except IngestionError as error:
            reviews.append({"url": claim["url"], "status": "unverified", "reason": error.code})
    return enriched, reviews


def exercise_year_bounds(record):
    if record.get("year_start") is not None:
        return record["year_start"], record["year_end"]
    starts_on = date.fromisoformat(record["starts_on"])
    end = record.get("ends_before")
    last_on = date.fromisoformat(end) - timedelta(days=1) if end else date.fromisoformat(
        record["observed_through"])
    return starts_on.year, last_on.year


def apply_reviewed_display_name(record, claim, evidence):
    if not claim.get("display_name"):
        return
    record["original_source_name"] = record["name"]
    record["name"] = claim["display_name"]
    record["display_name_evidence"] = evidence
