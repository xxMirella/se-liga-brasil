"""Acquisition locks and identity composition must stay idempotent and bounded."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from service.crawling import acquisition, alesp_pipeline
from service.ingestion.contracts import DownloadedArtifact, IngestionError, Resource


def resource(key):
    return Resource(key, "Test resource", "https://www.al.sp.gov.br/resource", "payroll", 2024, key)


def test_local_lock_rejects_overlap_and_releases_after_exception(tmp_path):
    with pytest.raises(ValueError), acquisition.local_run_lock(tmp_path):
        with (
            pytest.raises(IngestionError, match="CRAWLER_ALREADY_RUNNING_LOCALLY"),
            acquisition.local_run_lock(tmp_path),
        ):
            pytest.fail("Second process must not enter the critical section")
        raise ValueError("cancelled")
    with acquisition.local_run_lock(tmp_path):
        assert (tmp_path / ".crawler.lock").stat().st_mode & 0o777 == 0o600


def test_download_budget_is_shared_and_failure_does_not_discard_successes(monkeypatch, tmp_path):
    budgets = []

    def download(item, configuration, client, budget, progress):
        budgets.append(budget)
        if item.resource_id == "bad":
            raise IngestionError("INVALID_NUMERIC_FORMAT")
        return DownloadedArtifact(
            item, tmp_path / "original.zip", "a" * 64, "2024-01-01", 12, "cached"
        )

    monkeypatch.setattr(acquisition, "download_resource", download)
    configuration = SimpleNamespace(storage_directory=tmp_path)
    downloads, failures = acquisition.download_selected_resources(
        configuration, None, [resource("bad"), resource("good")]
    )
    assert len(downloads) == len(failures) == 1
    assert budgets[0] is budgets[1]
    assert downloads[0].acquisition_status == "cached"
    assert (tmp_path / "download-plan.json").exists()


@pytest.mark.parametrize(
    "phase,has_repository,expected",
    [
        ("discover", False, False),
        ("download", True, False),
        ("run", True, True),
        ("ingest", True, True),
        ("resolve-identities", True, True),
    ],
)
def test_alesp_identity_resolution_only_follows_ingestion(
    monkeypatch, tmp_path, phase, has_repository, expected
):
    configuration = SimpleNamespace(storage_directory=tmp_path)
    connection = SimpleNamespace(
        execute=Mock(
            return_value=SimpleNamespace(
                fetchall=lambda: [{"identity_status": "verified", "total": 1}]
            )
        )
    )
    repository = SimpleNamespace(connection=connection, source_id=1) if has_repository else None
    pipeline = Mock(return_value={"artifacts": [], "failures": []})
    monkeypatch.setattr(alesp_pipeline, "run_source_pipeline", pipeline)
    monkeypatch.setattr(alesp_pipeline, "collect_identity_evidence", lambda *_: ["identity"])
    monkeypatch.setattr(alesp_pipeline, "collect_reviewed_identities", lambda *_: ["reviewed"])
    resolve = Mock(return_value={"resolutions": [], "unresolved": [], "unresolved_recipients": 2})
    monkeypatch.setattr(alesp_pipeline, "resolve_payroll_identities", resolve)
    monkeypatch.setattr(alesp_pipeline, "save_alesp_affiliation_reports", lambda *_: {})
    monkeypatch.setattr(alesp_pipeline, "verify_payroll_political_parties", lambda *_: {})
    result = alesp_pipeline.run_alesp_pipeline(phase, configuration, None, repository)
    assert resolve.call_count == int(expected)
    assert pipeline.call_count == int(phase != "resolve-identities")
    if expected:
        assert result["identity_unresolved"] == 2
        assert "resolutions" not in result["identity_resolution"]
        assert result["payroll_identity_coverage"] == {"verified": 1}
