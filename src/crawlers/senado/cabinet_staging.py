"""Reconcile an entire cabinet/month fact atomically through shared provenance storage."""

from service.ingestion.contracts import ValidatedArtifact
from storage.files import create_private_directory, hash_content, hash_file, write_json_line

PARSER_VERSION = "senado-cabinet-payroll-python-v3"


class CabinetPayrollProjectionWriter:
    def __init__(self, writer):
        self.writer = writer

    def project_batch(self, parameters, resource_kind):
        self.writer.execute_statements("senado_common", parameters)


def stage_cabinet_payroll(artifact, configuration, records):
    scope = "senado:cabinet-payroll:" + hash_content([r["personId"] for r in records])
    directory = (
        configuration.storage_directory
        / "validated"
        / hash_content([artifact.sha256, PARSER_VERSION, scope])
    )
    create_private_directory(directory)
    path, rejected = directory / "records.ndjson", directory / "rejected.ndjson"
    with path.open("w", encoding="utf-8") as output:
        path.chmod(0o600)
        for number, data in enumerate(records, start=1):
            write_json_line(
                output,
                {
                    "kind": "senado_cabinet_payroll",
                    "externalKey": data["personId"] + ":" + data["period"] + ":v3",
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
        path,
        rejected,
        hash_file(path),
        hash_file(rejected),
        scope,
        {"valid": len(records), "rejected": 0},
        PARSER_VERSION,
    )
