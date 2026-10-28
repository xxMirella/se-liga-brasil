"""Hash and stage independently identified synopsis events and rejected rows."""

from service.ingestion.contracts import ValidatedArtifact
from storage.files import create_private_directory, hash_content, hash_file, write_json_line

PARSER_VERSION = "alerj-historical-narratives-python-v1"


def stage_historical_events(artifact, storage, rows, rejections):
    scope = hash_content(sorted({row["personId"] for row in rows}))
    directory = storage / "validated" / f"{artifact.sha256}-{PARSER_VERSION}-{scope}"
    create_private_directory(directory)
    records, rejected = directory / "records.ndjson", directory / "rejected.ndjson"
    with records.open("w", encoding="utf-8") as output:
        records.chmod(0o600)
        for number, row in enumerate(rows, 1):
            write_json_line(
                output,
                {
                    "kind": artifact.resource.kind,
                    "externalKey": row["personId"] + ":" + row["eventKey"],
                    "normalizedData": row,
                    "contentSha256": hash_content(
                        {key: value for key, value in row.items() if key != "storageReference"}
                    ),
                    "sourceGeneratedAt": artifact.fetched_at,
                    "entryName": artifact.path.name,
                    "rowNumber": number,
                },
            )
    with rejected.open("w", encoding="utf-8") as output:
        rejected.chmod(0o600)
        for failure in rejections:
            write_json_line(
                output,
                {
                    "resourceId": artifact.resource.resource_id,
                    "entryName": artifact.path.name,
                    "rowNumber": failure["page"],
                    "reasonCode": failure["reasonCode"],
                    "details": {"pdfPage": failure["page"]},
                },
            )
    return ValidatedArtifact(
        artifact,
        records,
        rejected,
        hash_file(records),
        hash_file(rejected),
        "alerj-history:" + scope,
        {"valid": len(rows), "rejected": len(rejections)},
        PARSER_VERSION,
    )
