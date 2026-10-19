"""Stage personally verified observations for shared idempotent reconciliation."""

from crawlers.alerj.configuration import PARSER_VERSION
from service.ingestion.contracts import ValidatedArtifact
from storage.files import create_private_directory, hash_content, hash_file, write_json_line


def stage_records(artifact, configuration, rows):
    scope = hash_content([row["personId"] for row in rows])
    directory = configuration.storage_directory / "validated" / (artifact.sha256 + "-" + scope)
    create_private_directory(directory)
    records, rejected = directory / "records.ndjson", directory / "rejected.ndjson"
    with records.open("w", encoding="utf-8") as output:
        records.chmod(0o600)
        for number, row in enumerate(rows, start=1):
            key = row["personId"] + (":" + row["competence"] if "competence" in row else "")
            write_json_line(
                output,
                {
                    "kind": artifact.resource.kind,
                    "externalKey": key,
                    "normalizedData": row,
                    "contentSha256": hash_content(row),
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
        "alerj:" + scope,
        {"valid": len(rows), "rejected": 0},
        PARSER_VERSION,
    )
