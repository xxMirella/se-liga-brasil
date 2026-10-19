"""Stage source-backed records for the existing generic ingestion repository."""

from crawlers.camara.configuration import PARSER_VERSION
from service.ingestion.contracts import ValidatedArtifact
from storage.files import create_private_directory, hash_content, hash_file, write_json_line


def stage_records(artifact, configuration, data_rows) -> ValidatedArtifact:
    directory = (
        configuration.storage_directory / "validated" / (artifact.sha256 + "-" + PARSER_VERSION)
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
        staging_scope(artifact.resource.kind, data_rows),
        {"valid": len(data_rows), "rejected": 0},
        PARSER_VERSION,
    )


def record_key(kind, data) -> str:
    if kind.startswith("camara_legislative_") or kind == "camara_attendance":
        return data["recordKey"]
    if kind == "camara_profile":
        return data["personId"]
    if kind == "camara_payroll":
        return data["personId"] + ":" + data["competence"]
    return hash_content([data["personId"], data["officialKey"]])


def staging_scope(kind, rows):
    if not kind.startswith("camara_legislative_") and kind != "camara_attendance":
        return "camara:personal-enrichment"
    keys = [row["recordKey"] for row in rows]
    return "camara:legislative:" + hash_content([kind, keys])
