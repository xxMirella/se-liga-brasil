"""Pipeline orchestration: discover, download, validate and ingest are independent phases."""

from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from crawlers.tse.discovery import discover_resources, is_selected_resource
from crawlers.tse.validator import deserialize_validation, serialize_validation, validate_resource
from database.operations import refresh_person_profiles
from service.crawling.acquisition import download_selected_resources, local_run_lock
from service.crawling.ingestion import (
    build_resource_failure,
    ingest_validation_plan,
    report_validation_rejections,
)
from service.ingestion.contracts import DownloadedArtifact, IngestionError, Resource
from service.observability.reporting import emit_event
from storage.files import load_json, save_json
from storage.validation_index import ValidationIndex


def load_download_plan(configuration) -> list[DownloadedArtifact]:
    plan = load_json(configuration.storage_directory / "download-plan.json", [])
    downloads = []
    for item in plan:
        resource = Resource(**item["resource"])
        if not is_selected_resource(resource, configuration):
            continue
        if configuration.years and resource.year not in configuration.years:
            continue
        downloads.append(
            DownloadedArtifact(
                resource,
                Path(item["path"]),
                item["sha256"],
                item["fetched_at"],
                item["bytes_downloaded"],
                item.get("acquisition_status", "downloaded"),
            )
        )
    return downloads


def validate_downloaded_resources(configuration, downloads) -> tuple[list, list]:
    validations = []
    failures = []
    index_path = configuration.storage_directory / f"validation-index-{uuid4().hex}.sqlite"
    index = ValidationIndex(index_path)
    try:
        for artifact in downloads:
            validate_selected_artifact(artifact, configuration, index, validations, failures)
    finally:
        index.close()
        index_path.unlink(missing_ok=True)
    save_json(
        configuration.storage_directory / "validation-plan.json",
        [serialize_validation(validated) for validated in validations],
    )
    return validations, failures


def validate_selected_artifact(artifact, configuration, index, validations, failures) -> None:
    try:
        emit_event("validate_started", resource_name=artifact.resource.name)
        validated = validate_resource(artifact, configuration, index)
        validations.append(validated)
        report_validation_rejections(validated)
        emit_event("validate", resource_id=artifact.resource.resource_id, **validated.summary)
    except Exception as error:
        failures.append(build_resource_failure(artifact.resource, error, "validate"))


def run_pipeline(phase, configuration, client, repository=None) -> dict:
    with local_run_lock(configuration.storage_directory):
        return execute_pipeline_phase(phase, configuration, client, repository)


def execute_pipeline_phase(phase, configuration, client, repository) -> dict:
    failures = []
    if phase == "discover":
        resources = discover_resources(configuration, client)
        emit_event("discovery", total_files=len(resources))
        save_json(
            configuration.storage_directory / "discovery-plan.json",
            [asdict(resource) for resource in resources],
        )
        return {"resources": len(resources)}
    if phase in {"download", "run"}:
        resources = discover_resources(configuration, client)
        downloads, failures = download_selected_resources(configuration, client, resources)
    else:
        downloads = load_download_plan(configuration)
    if phase == "download":
        return {"downloaded": len(downloads), "failures": failures}
    return execute_validation_phase(phase, configuration, downloads, repository, failures)


def execute_validation_phase(phase, configuration, downloads, repository, failures) -> dict:
    if phase in {"validate", "run"}:
        validations, validation_failures = validate_downloaded_resources(configuration, downloads)
        failures.extend(validation_failures)
    else:
        manifests = load_json(configuration.storage_directory / "validation-plan.json", [])
        validations = [deserialize_validation(manifest) for manifest in manifests]
        if any(item.scope_key != configuration.scope_key for item in validations):
            raise IngestionError("STAGING_SCOPE_MISMATCH")
    if phase == "validate":
        return {"validated": len(validations), "failures": failures}
    if not validations:
        raise IngestionError("NO_VALIDATED_ARTIFACTS")
    summaries = ingest_validation_plan(configuration, repository, validations, failures)
    refresh_profiles_with_progress(repository.connection)
    result = {
        "artifacts": summaries,
        "failures": failures,
        "finished_at": datetime.now(UTC).isoformat(),
    }
    save_json(configuration.storage_directory / "last-run.json", result)
    return result


def refresh_profiles_with_progress(connection) -> None:
    emit_event("profiles_refresh_started", resource_name="Atualizando consulta de perfis")
    refresh_person_profiles(connection)
    emit_event("profiles_refresh_finished")
