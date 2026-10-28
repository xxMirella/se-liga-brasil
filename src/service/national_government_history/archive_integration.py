"""Integrate one previously archived official article without repeating source collections."""

from crawlers.state_government.parsing import visible_text
from service.ingestion.contracts import IngestionError
from service.national_government_history.collection import annual_observation, observation_coverage
from service.national_government_history.current_2026 import CURRENT_2026_OBSERVATIONS


def normalize_catalog_archive(artifact):
    rows = [row for row in CURRENT_2026_OBSERVATIONS if row[6] == artifact.resource.url]
    if len(rows) != 1:
        raise IngestionError("OFFICIAL_GOVERNMENT_ARCHIVE_CATALOG_MATCH_REQUIRED")
    uf, name, party, observed, published, kind, _, locators = rows[0]
    return annual_observation(
        artifact,
        visible_text(artifact.path.read_bytes()),
        uf=uf,
        name=name,
        party=party,
        observed_on=observed,
        published_on=published,
        kind=kind,
        locators=locators,
    )


def merge_archived_observation(payload, record):
    if payload.get("schema_version") != "national_government_observations.v1":
        raise IngestionError("UNSUPPORTED_EXECUTIVE_EVIDENCE_SCHEMA")
    identity = observation_identity(record)
    records = [old for old in payload["exercises"] if observation_identity(old) != identity]
    records.append(record)
    return {**payload, "exercises": records, "coverage": observation_coverage(records)}


def observation_identity(record):
    return (
        record["territory_code"],
        record["institution_code"],
        record.get("source_url"),
        record.get("source_observed_on"),
    )
