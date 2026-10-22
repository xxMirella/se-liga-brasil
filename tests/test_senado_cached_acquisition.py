"""Offline replay accepts only intact archived official resources and never falls back to HTTP."""

import json
from datetime import date

import pytest

from crawlers.senado.acquisition import json_resource
from crawlers.senado.cached_acquisition import CachedSenateAcquisition
from crawlers.senado.configuration import SenateConfiguration
from crawlers.senado.voting_pipeline import collect_senate_voting_partitions
from service.ingestion.contracts import IngestionError
from storage.files import hash_file, save_json


def test_missing_offline_archive_does_not_attempt_remote_recovery(tmp_path):
    acquisition = CachedSenateAcquisition(SenateConfiguration(tmp_path))
    with pytest.raises(IngestionError, match="OFFLINE_ARCHIVE_MISSING_OR_CHANGED"):
        acquisition.json_document("votacao.json?dataInicio=2026-10-14", "senado_votings")


def test_replay_preserves_observation_date_and_rejects_tampered_archive(tmp_path):
    acquisition = CachedSenateAcquisition(SenateConfiguration(tmp_path))
    resource = json_resource("votacao.json", "senado_votings")
    original = tmp_path / "archive.json"
    original.write_text(json.dumps([]))
    observed = "2026-10-17T12:00:00+00:00"
    save_json(tmp_path / "manifests" / f"{resource.resource_id}.json", {
        "source_url": resource.url, "path": str(original), "sha256": hash_file(original),
        "fetched_at": observed, "bytes": original.stat().st_size,
    })
    document, artifact = acquisition.json_document("votacao.json", "senado_votings")
    assert document == [] and artifact.fetched_at == observed
    original.write_text("changed")
    with pytest.raises(IngestionError, match="OFFLINE_ARCHIVE_MISSING_OR_CHANGED"):
        acquisition.json_document("votacao.json", "senado_votings")


def test_offline_mode_rejects_profile_downloads_before_database_access(tmp_path):
    with pytest.raises(IngestionError, match="OFFLINE_VOTING_CANNOT_DOWNLOAD"):
        collect_senate_voting_partitions(
            None, tmp_path, date(2026, 10, 14), date(2026, 10, 14),
            local_only=True, max_identity_profile_downloads=1,
        )
