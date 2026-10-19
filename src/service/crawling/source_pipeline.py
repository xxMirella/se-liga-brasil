"""Reusable phases for sources with independent resource validators."""

from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from service.crawling.acquisition import download_selected_resources, local_run_lock
from service.crawling.ingestion import (
    build_resource_failure,
    ingest_validation_plan,
    report_validation_rejections,
)
from service.ingestion.contracts import DownloadedArtifact, IngestionError, Resource
from service.observability.reporting import emit_event
from storage.files import load_json, save_json
from storage.staging import deserialize_validation, serialize_validation


def load_selected_downloads(configuration, select_resource) -> list:
    downloads = []
    for item in load_json(configuration.storage_directory / "download-plan.json", []):
        resource = Resource(**item["resource"])
        if select_resource(resource, configuration):
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


def validate_artifacts(configuration, downloads, validate_resource) -> tuple[list, list]:
    validations, failures = [], []
    for artifact in downloads:
        try:
            emit_event("validate_started", resource_name=artifact.resource.name)
            validated = validate_resource(artifact, configuration)
            validations.append(validated)
            report_validation_rejections(validated)
            emit_event("validate", resource_id=artifact.resource.resource_id, **validated.summary)
        except Exception as error:
            failures.append(build_resource_failure(artifact.resource, error, "validate"))
    save_json(
        configuration.storage_directory / "validation-plan.json",
        [serialize_validation(item) for item in validations],
    )
    return validations, failures


def load_selected_validations(configuration, select_resource) -> list:
    items = load_json(configuration.storage_directory / "validation-plan.json", [])
    validations = [deserialize_validation(item) for item in items]
    selected = [
        item for item in validations if select_resource(item.artifact.resource, configuration)
    ]
    if any(item.scope_key != configuration.scope_key for item in selected):
        raise IngestionError("STAGING_SCOPE_MISMATCH")
    return selected


def run_source_pipeline(phase, configuration, client, repository, adapter) -> dict:
    with local_run_lock(configuration.storage_directory):
        return execute_source_phase(phase, configuration, client, repository, adapter)


def execute_source_phase(phase, configuration, client, repository, adapter) -> dict:
    failures = []
    if phase in {"discover", "download", "run"}:
        resources = adapter.discover_resources(configuration, client)
        save_json(
            configuration.storage_directory / "discovery-plan.json", [asdict(r) for r in resources]
        )
        emit_event("discovery", total_files=len(resources))
        if phase == "discover":
            return {"resources": len(resources)}
        downloads, failures = download_selected_resources(configuration, client, resources)
    else:
        downloads = load_selected_downloads(configuration, adapter.is_selected_resource)
    if phase == "download":
        return {"downloaded": len(downloads), "failures": failures}
    if phase in {"validate", "run"}:
        validations, errors = validate_artifacts(
            configuration, downloads, adapter.validate_resource
        )
        failures.extend(errors)
    else:
        validations = load_selected_validations(configuration, adapter.is_selected_resource)
    if phase == "validate":
        return {"validated": len(validations), "failures": failures}
    if not validations:
        raise IngestionError("NO_VALIDATED_ARTIFACTS")
    summaries = ingest_validation_plan(configuration, repository, validations, failures)
    result = {
        "artifacts": summaries,
        "failures": failures,
        "finished_at": datetime.now(UTC).isoformat(),
    }
    save_json(configuration.storage_directory / "last-run.json", result)
    return result
