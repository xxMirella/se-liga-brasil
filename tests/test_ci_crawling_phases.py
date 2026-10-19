"""Independent crawling phases preserve staging scope, errors and effect ordering."""

from contextlib import contextmanager
from dataclasses import asdict
from types import SimpleNamespace

import pytest

from service.crawling import source_pipeline, tse_pipeline
from service.ingestion.contracts import (
    DownloadedArtifact,
    IngestionError,
    Resource,
    ValidatedArtifact,
)
from storage.files import load_json, save_json
from storage.staging import serialize_validation


@pytest.fixture
def phase_files(tmp_path):
    config = SimpleNamespace(storage_directory=tmp_path, scope_key="scope", years=[2026])
    resource = Resource(
        "resource",
        "candidate.zip",
        "https://example.invalid/file",
        "candidate",
        2026,
        "dataset",
        "SP",
    )
    artifact = DownloadedArtifact(
        resource, tmp_path / "raw.zip", "a" * 64, "2026-05-01T00:00:00Z", 10
    )
    validated = ValidatedArtifact(
        artifact,
        tmp_path / "records",
        tmp_path / "rejected",
        "b" * 64,
        "c" * 64,
        "scope",
        {"accepted": 1},
    )
    return config, resource, artifact, validated


def write_downloads(config, artifacts):
    rows = []
    for artifact in artifacts:
        row = asdict(artifact)
        row["path"] = str(artifact.path)
        rows.append(row)
    save_json(config.storage_directory / "download-plan.json", rows)


@pytest.mark.parametrize("module", [source_pipeline, tse_pipeline])
def test_download_plan_filters_before_returning_artifacts(monkeypatch, phase_files, module):
    config, resource, artifact, _ = phase_files
    write_downloads(config, [artifact])
    if module is tse_pipeline:
        monkeypatch.setattr(module, "is_selected_resource", lambda *args: False)
        assert module.load_download_plan(config) == []
        monkeypatch.setattr(module, "is_selected_resource", lambda *args: True)
        assert module.load_download_plan(config) == [artifact]
        config.years = [2024]
        assert module.load_download_plan(config) == []
    else:
        assert module.load_selected_downloads(config, lambda *args: False) == []
        assert module.load_selected_downloads(config, lambda *args: True) == [artifact]


def test_legacy_download_plan_defaults_acquisition_status(phase_files):
    config, _, artifact, _ = phase_files
    write_downloads(config, [artifact])
    path = config.storage_directory / "download-plan.json"
    rows = load_json(path)
    rows[0].pop("acquisition_status")
    save_json(path, rows)
    assert (
        source_pipeline.load_selected_downloads(config, lambda *args: True)[0].acquisition_status
        == "downloaded"
    )


def test_generic_validation_selects_scope_only_after_resource_filter(phase_files):
    config, _, _, validated = phase_files
    save_json(config.storage_directory / "validation-plan.json", [serialize_validation(validated)])
    assert source_pipeline.load_selected_validations(config, lambda *args: True) == [validated]
    config.scope_key = "other"
    assert source_pipeline.load_selected_validations(config, lambda *args: False) == []
    with pytest.raises(IngestionError, match="STAGING_SCOPE_MISMATCH"):
        source_pipeline.load_selected_validations(config, lambda *args: True)


@pytest.mark.parametrize("module", [source_pipeline, tse_pipeline])
def test_validation_failure_does_not_discard_later_valid_artifact(monkeypatch, phase_files, module):
    config, _, artifact, validated = phase_files
    attempts, reported = [], []

    def validate(item, configuration, *index):
        attempts.append(item)
        if len(attempts) == 1:
            raise IngestionError("INVALID_NUMERIC_FORMAT")
        return validated

    monkeypatch.setattr(module, "report_validation_rejections", lambda item: reported.append(item))
    monkeypatch.setattr(module, "emit_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        module,
        "build_resource_failure",
        lambda resource, error, phase: {"code": str(error), "phase": phase},
    )
    if module is source_pipeline:
        accepted, failures = module.validate_artifacts(config, [artifact, artifact], validate)
    else:
        monkeypatch.setattr(module, "validate_resource", validate)
        accepted, failures = module.validate_downloaded_resources(config, [artifact, artifact])
        assert not list(config.storage_directory.glob("validation-index-*.sqlite"))
    assert accepted == [validated]
    assert reported == [validated]
    assert failures == [{"code": "INVALID_NUMERIC_FORMAT", "phase": "validate"}]
    assert len(load_json(config.storage_directory / "validation-plan.json")) == 1


@pytest.fixture(params=[source_pipeline, tse_pipeline])
def phase_runner(request, monkeypatch, phase_files):
    module = request.param
    config, resource, artifact, validated = phase_files
    effects = []
    adapter = SimpleNamespace(
        discover_resources=lambda *args: effects.append("discover") or [resource],
        is_selected_resource=lambda *args: True,
        validate_resource=lambda *args: validated,
    )
    monkeypatch.setattr(module, "emit_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        module,
        "download_selected_resources",
        lambda *args: effects.append("download") or ([artifact], [{"phase": "download"}]),
    )
    monkeypatch.setattr(
        module, "ingest_validation_plan", lambda *args: effects.append("ingest") or [{"new": 1}]
    )
    write_downloads(config, [artifact])
    save_json(config.storage_directory / "validation-plan.json", [serialize_validation(validated)])
    if module is source_pipeline:
        monkeypatch.setattr(
            module,
            "validate_artifacts",
            lambda *args: effects.append("validate") or ([validated], [{"phase": "validate"}]),
        )
    else:
        monkeypatch.setattr(module, "discover_resources", adapter.discover_resources)
        monkeypatch.setattr(module, "is_selected_resource", adapter.is_selected_resource)
        monkeypatch.setattr(
            module,
            "validate_downloaded_resources",
            lambda *args: effects.append("validate") or ([validated], [{"phase": "validate"}]),
        )
        monkeypatch.setattr(
            module, "refresh_profiles_with_progress", lambda *args: effects.append("refresh")
        )

    def run(phase):
        repository = SimpleNamespace(connection="connection")
        if module is source_pipeline:
            return module.execute_source_phase(phase, config, None, repository, adapter)
        return module.execute_pipeline_phase(phase, config, None, repository)

    return module, config, effects, run


def test_discovery_stops_before_download_and_records_manifest(phase_runner):
    _, config, effects, run = phase_runner
    assert run("discover") == {"resources": 1}
    assert effects == ["discover"]
    assert len(load_json(config.storage_directory / "discovery-plan.json")) == 1
    assert not (config.storage_directory / "last-run.json").exists()


def test_download_stops_before_validation_and_returns_partial_failures(phase_runner):
    _, _, effects, run = phase_runner
    assert run("download") == {"downloaded": 1, "failures": [{"phase": "download"}]}
    assert effects == ["discover", "download"]


def test_validate_uses_saved_downloads_without_redownloading(phase_runner):
    _, _, effects, run = phase_runner
    assert run("validate") == {"validated": 1, "failures": [{"phase": "validate"}]}
    assert effects == ["validate"]


def test_full_run_keeps_phase_order_and_all_failures(phase_runner):
    module, config, effects, run = phase_runner
    result = run("run")
    expected = ["discover", "download", "validate", "ingest"]
    if module is tse_pipeline:
        expected.append("refresh")
    assert effects == expected
    assert result["failures"] == [{"phase": "download"}, {"phase": "validate"}]
    assert result["artifacts"] == [{"new": 1}]
    assert load_json(config.storage_directory / "last-run.json") == result


def test_ingest_uses_saved_validation_without_discovery_or_revalidation(phase_runner):
    module, _, effects, run = phase_runner
    assert run("ingest")["artifacts"] == [{"new": 1}]
    assert effects == (["ingest", "refresh"] if module is tse_pipeline else ["ingest"])


def test_ingest_scope_mismatch_blocks_projection_and_profile_refresh(phase_runner):
    _, config, effects, run = phase_runner
    config.scope_key = "different-scope"
    with pytest.raises(IngestionError, match="STAGING_SCOPE_MISMATCH"):
        run("ingest")
    assert effects == []


def test_ingest_empty_staging_is_not_successful_run(phase_runner):
    _, config, effects, run = phase_runner
    save_json(config.storage_directory / "validation-plan.json", [])
    with pytest.raises(IngestionError, match="NO_VALIDATED_ARTIFACTS"):
        run("ingest")
    assert effects == []
    assert not (config.storage_directory / "last-run.json").exists()


@pytest.mark.parametrize("module", [source_pipeline, tse_pipeline])
def test_run_lock_is_released_when_phase_raises(monkeypatch, phase_files, module):
    config, _, _, _ = phase_files
    events = []

    @contextmanager
    def lock(directory):
        assert directory == config.storage_directory
        events.append("locked")
        try:
            yield
        finally:
            events.append("unlocked")

    def fail(*args):
        raise IngestionError("TEST_DISCOVERY_FAILURE")

    monkeypatch.setattr(module, "local_run_lock", lock)
    if module is source_pipeline:
        monkeypatch.setattr(module, "execute_source_phase", fail)

        def invoke():
            return module.run_source_pipeline("run", config, None, None, None)
    else:
        monkeypatch.setattr(module, "execute_pipeline_phase", fail)

        def invoke():
            return module.run_pipeline("run", config, None)

    with pytest.raises(IngestionError, match="TEST_DISCOVERY_FAILURE"):
        invoke()
    assert events == ["locked", "unlocked"]


def test_profile_refresh_reports_finished_only_after_database_effect(monkeypatch):
    effects = []
    monkeypatch.setattr(tse_pipeline, "emit_event", lambda event, **kwargs: effects.append(event))
    monkeypatch.setattr(
        tse_pipeline,
        "refresh_person_profiles",
        lambda connection: effects.append("database-refresh"),
    )
    tse_pipeline.refresh_profiles_with_progress(None)
    assert effects == ["profiles_refresh_started", "database-refresh", "profiles_refresh_finished"]
