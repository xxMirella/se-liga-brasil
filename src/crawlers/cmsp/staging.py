"""Validate a complete partition before exposing derived NDJSON for ingestion."""

from uuid import uuid4

from crawlers.cmsp.configuration import PARSER_VERSION
from crawlers.cmsp.normalization import attach_reviewed_authors, normalize_project
from crawlers.cmsp.parsing import iter_projects
from service.ingestion.contracts import IngestionError, ValidatedArtifact
from storage.files import create_private_directory, hash_content, hash_file, write_json_line


def stage_partition(artifact, configuration, bindings):
    if hash_file(artifact.path) != artifact.sha256:
        raise IngestionError("CMSP_ARTIFACT_CHANGED")
    directory = configuration.storage_directory / "validated" / artifact.sha256 / uuid4().hex
    create_private_directory(directory)
    records, rejected = directory / "records.ndjson", directory / "rejected.ndjson"
    counts = {"valid": 0, "rejected": 0}
    seen = {}
    try:
        with (
            records.open("x", encoding="utf-8") as output,
            rejected.open("x", encoding="utf-8") as failures,
        ):
            records.chmod(0o600)
            rejected.chmod(0o600)
            projects = iter_projects(
                artifact.path, max_records=configuration.max_records_per_resource
            )
            for row_number, project in enumerate(projects, 1):
                stage_project(
                    project, row_number, artifact, bindings, output, failures, counts, seen
                )
    except Exception:
        records.unlink(missing_ok=True)
        rejected.unlink(missing_ok=True)
        directory.rmdir()
        raise
    return ValidatedArtifact(
        artifact,
        records,
        rejected,
        hash_file(records),
        hash_file(rejected),
        f"cmsp:{artifact.resource.kind}:{artifact.resource.year}:{reviewed_scope(bindings)}",
        counts,
        PARSER_VERSION,
    )


def stage_project(project, row_number, artifact, bindings, output, failures, counts, seen):
    try:
        data = normalize_project(project, artifact.resource.year)
        data = attach_reviewed_authors(data, bindings, artifact.sha256)
        digest = hash_content(data)
        key = data["officialKey"]
        if key in seen:
            if seen[key] != digest:
                raise IngestionError("CMSP_CONFLICTING_DUPLICATE_PROPOSITION")
            return
        seen[key] = digest
        write_json_line(
            output,
            {
                "kind": artifact.resource.kind,
                "externalKey": staged_record_key(key, data),
                "normalizedData": data,
                "contentSha256": digest,
                "sourceGeneratedAt": artifact.fetched_at,
                "entryName": artifact.path.name,
                "rowNumber": row_number,
            },
        )
        counts["valid"] += 1
    except IngestionError as error:
        if (
            error.code.startswith("CMSP_REVIEWED_")
            or error.code == "CMSP_CONFLICTING_DUPLICATE_PROPOSITION"
        ):
            raise
        write_json_line(
            failures,
            {
                "resourceId": artifact.resource.resource_id,
                "entryName": artifact.path.name,
                "rowNumber": row_number,
                "reasonCode": error.code,
                "payloadSha256": hash_content([artifact.sha256, row_number]),
                "details": error.details,
            },
        )
        counts["rejected"] += 1


def reviewed_scope(bindings):
    evidence = {
        name: {
            "personId": str(binding.person_id),
            "evidence": binding.evidence_reference,
            "artifactSha256": binding.artifact_sha256,
            "method": binding.method,
        }
        for name, binding in bindings.items()
    }
    return hash_content(evidence)


def staged_record_key(project_key, data):
    if not data["verifiedAuthors"]:
        return project_key
    return project_key + ":reviewed:" + hash_content(data["verifiedAuthors"])
