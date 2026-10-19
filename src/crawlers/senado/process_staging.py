"""Whitelist official process descriptions; personal provider keys stay in originals."""

from uuid import uuid4

from normalization.scalars import normalize_text
from service.ingestion.contracts import ValidatedArtifact
from storage.files import create_private_directory, hash_content, hash_file, write_json_line

PARSER_VERSION = "senado-process-summary-v1"


def process_summary_record(process):
    return {
        "source_key": process["source_key"],
        "kind": process["kind"],
        "number": process["number"],
        "year": process["year"],
        "summary": normalize_text(process.get("description"), max_length=100000),
        "official_url": "https://legis.senado.leg.br/dadosabertos/processo/"
        + process["source_key"],
        "summary_origin": "official_text",
    }


def stage_process_summary(artifact, configuration, process):
    directory = configuration.storage_directory / "validated" / artifact.sha256 / uuid4().hex
    create_private_directory(directory)
    records, rejected = directory / "records.ndjson", directory / "rejected.ndjson"
    data = process_summary_record(process)
    with records.open("x", encoding="utf-8") as output:
        records.chmod(0o600)
        write_json_line(
            output,
            {
                "kind": "senado_process_summary",
                "externalKey": data["source_key"],
                "normalizedData": data,
                "contentSha256": hash_content(data),
                "sourceGeneratedAt": artifact.fetched_at,
                "entryName": artifact.path.name,
                "rowNumber": 1,
            },
        )
    rejected.write_text("", encoding="utf-8")
    rejected.chmod(0o600)
    return ValidatedArtifact(
        artifact,
        records,
        rejected,
        hash_file(records),
        hash_file(rejected),
        "senado:process-summary",
        {"valid": 1, "rejected": 0},
        PARSER_VERSION,
    )


class SenateProcessSummaryProjection:
    def __init__(self, writer):
        self.writer = writer

    def project_batch(self, parameters, resource_kind):
        self.writer.execute_statements("senado_process_details", parameters)
