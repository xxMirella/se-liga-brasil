"""Portable manifests for validated artifacts from every source."""

from pathlib import Path

from service.ingestion.contracts import DownloadedArtifact, ValidatedArtifact


def serialize_validation(validated: ValidatedArtifact) -> dict:
    from dataclasses import asdict

    manifest = asdict(validated)
    manifest["artifact"]["path"] = str(validated.artifact.path)
    manifest["records_path"] = str(validated.records_path)
    manifest["rejected_path"] = str(validated.rejected_path)
    return manifest


def deserialize_validation(manifest: dict) -> ValidatedArtifact:
    from service.ingestion.contracts import Resource

    artifact_data = manifest["artifact"]
    artifact = DownloadedArtifact(
        Resource(**artifact_data["resource"]),
        Path(artifact_data["path"]),
        artifact_data["sha256"],
        artifact_data["fetched_at"],
        artifact_data["bytes_downloaded"],
        artifact_data.get("acquisition_status", "downloaded"),
    )
    return ValidatedArtifact(
        artifact,
        Path(manifest["records_path"]),
        Path(manifest["rejected_path"]),
        manifest["records_sha256"],
        manifest["rejected_sha256"],
        manifest["scope_key"],
        manifest["summary"],
        manifest["parser_version"],
    )
