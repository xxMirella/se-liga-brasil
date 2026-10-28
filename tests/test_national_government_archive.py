"""Preserve archived evidence without projecting old affiliation forward."""

import pytest

from service.ingestion.contracts import DownloadedArtifact, IngestionError, Resource
from service.national_government_history.archive_integration import (
    merge_archived_observation,
    normalize_catalog_archive,
)
from service.national_government_history.current_2026 import RR_OCTOBER_URL
from storage.files import hash_file


def archived_article(tmp_path, text):
    path = tmp_path / "official.html"
    path.write_text(text)
    resource = Resource(
        "fixture", "fixture", RR_OCTOBER_URL, "government_observation", 2026, "isolated-fixture"
    )
    return DownloadedArtifact(resource, path, hash_file(path), "2026-10-24T23:46:00Z", 0)


def test_october_rr_office_observation_does_not_inherit_april_party(tmp_path):
    article = archived_article(
        tmp_path,
        "19 de outubro de 2026. O governador Soldado Sampaio recebeu nesta "
        "quinta-feira, 15, o governador eleito Arthur Henrique",
    )
    record = normalize_catalog_archive(article)
    april = {
        **record,
        "source_observed_on": "2026-04-30",
        "source_url": "https://al.rr.leg.br/posse",
        "political_party_abbreviation": "REPUBLICANOS",
    }
    payload = {"schema_version": "national_government_observations.v1", "exercises": [april]}
    once = merge_archived_observation(payload, record)
    twice = merge_archived_observation(once, record)
    assert once == twice
    assert len(twice["exercises"]) == 2
    assert twice["exercises"][0] == april
    assert record["source_observed_on"] == "2026-10-15"
    assert record["evidence"][0]["published_on"] == "2026-10-19"
    assert record["political_party_status"] == "unknown"
    assert "political_party_abbreviation" not in record
    assert record["starts_on"] is None and record["ends_before"] is None


def test_elected_successor_is_not_a_current_governor_observation(tmp_path):
    article = archived_article(
        tmp_path, "19 de outubro de 2026. O governador eleito Arthur Henrique"
    )
    with pytest.raises(IngestionError, match="SOURCE_CHANGED"):
        normalize_catalog_archive(article)
