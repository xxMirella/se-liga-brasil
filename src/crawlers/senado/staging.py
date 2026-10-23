"""Stage source-backed records for the existing generic ingestion repository."""

from crawlers.senado.configuration import PARSER_VERSION
from service.identity_resolution.evidence import IdentityEvidenceBuilder, load_identity_key
from service.ingestion.contracts import ValidatedArtifact
from storage.files import create_private_directory, hash_content, hash_file, write_json_line


def stage_records(artifact, configuration, data_rows) -> ValidatedArtifact:
    scope = staging_scope(artifact.resource.kind, data_rows)
    directory = (
        configuration.storage_directory
        / "validated"
        / (artifact.sha256 + "-" + PARSER_VERSION + "-" + hash_content(scope))
    )
    create_private_directory(directory)
    records, rejected = directory / "records.ndjson", directory / "rejected.ndjson"
    with records.open("w", encoding="utf-8") as output:
        records.chmod(0o600)
        for number, data in enumerate(data_rows, start=1):
            key = record_key(artifact.resource.kind, data)
            write_json_line(
                output,
                {
                    "kind": artifact.resource.kind,
                    "externalKey": key,
                    "normalizedData": data,
                    "contentSha256": hash_content(data),
                    "sourceGeneratedAt": artifact.fetched_at,
                    "entryName": artifact.path.name,
                    "rowNumber": number,
                    **institutional_identity_evidence(artifact.resource.kind, data),
                },
            )
    rejected.write_text("")
    rejected.chmod(0o600)
    return ValidatedArtifact(
        artifact,
        records,
        rejected,
        hash_file(records),
        hash_file(rejected),
        scope,
        {"valid": len(data_rows), "rejected": 0},
        PARSER_VERSION,
    )


def record_key(kind, data) -> str:
    if kind == "senado_institutional_profile":
        return data["officialSenatorCode"]
    if kind == "senado_payroll":
        return data["recipientKey"] + ":" + data["competence"]
    return data["personId"]


def institutional_identity_evidence(kind, data):
    if kind != "senado_institutional_profile":
        return {}
    builder = IdentityEvidenceBuilder(load_identity_key())
    return {"identityEvidence": builder.build_evidence(data["civilName"])}


def staging_scope(kind, rows):
    if kind == "senado_institutional_profile":
        return "senado:national-institutional-roster"
    if kind == "senado_payroll":
        return "senado:payroll:" + hash_content(sorted(row["personId"] for row in rows))
    return "senado:personal-enrichment"


def bundle_artifacts(configuration, profile, roster):
    from service.ingestion.contracts import DownloadedArtifact
    from storage.files import save_json

    references = [
        {"url": item.resource.url, "sha256": item.sha256, "path": str(item.path)}
        for item in (profile, roster)
    ]
    path = configuration.storage_directory / "bundles" / (hash_content(references) + ".json")
    if not path.exists():
        save_json(path, references)
    return DownloadedArtifact(
        profile.resource,
        path,
        hash_file(path),
        max(profile.fetched_at, roster.fetched_at),
        path.stat().st_size,
    )
