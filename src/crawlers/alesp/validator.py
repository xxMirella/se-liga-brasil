"""Validate schema, reference month, row uniqueness and exact monetary reconciliation."""

import re

from crawlers.alesp.configuration import ALESP_PARSER_VERSION
from crawlers.alesp.discovery import payroll_month
from crawlers.alesp.normalization import normalize_payroll_row
from normalization.text import fold_text
from parsing.html import HtmlTableParser, decode_html
from service.ingestion.contracts import IngestionError, ValidatedArtifact
from storage.files import create_private_directory, hash_content, hash_file, write_json_line

MONTH_NAMES = (
    "janeiro",
    "fevereiro",
    "marco",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
)


def parse_payroll_document(payload: bytes, competence: str) -> list[list[str]]:
    parser = HtmlTableParser("dados")
    parser.feed(decode_html(payload))
    text = fold_text(" ".join(parser.text))
    year, month = competence.split("-")
    reference = rf"mes de referencia:\s*{MONTH_NAMES[int(month) - 1]}\s*/\s*{year}\b"
    if not re.search(reference, text):
        raise IngestionError("PAYROLL_REFERENCE_MONTH_MISMATCH")
    if not parser.rows or len(parser.rows) > 5000:
        raise IngestionError("PAYROLL_SCHEMA_CHANGED")
    if not all(label in text for label in ("tributos", "bruta", "liquida")):
        raise IngestionError("PAYROLL_SCHEMA_CHANGED")
    return parser.rows


def stage_payroll_rows(artifact, rows, records, rejected) -> dict:
    seen = set()
    summary = {"valid": 0, "rejected": 0}
    for row_number, cells in enumerate(rows, start=1):
        try:
            data = normalize_payroll_row(cells, payroll_month(artifact.resource))
            key = f"{data['competence']}:{data['recipientKey']}"
            if key in seen:
                raise IngestionError("DUPLICATE_PAYROLL_RECIPIENT")
            seen.add(key)
            write_json_line(
                records,
                {
                    "kind": artifact.resource.kind,
                    "externalKey": key,
                    "normalizedData": data,
                    "contentSha256": hash_content(data),
                    "sourceGeneratedAt": artifact.fetched_at,
                    "entryName": artifact.path.name,
                    "rowNumber": row_number,
                    "diagnosticContext": {"competence": data["competence"]},
                },
            )
            summary["valid"] += 1
        except IngestionError as error:
            if error.code == "DUPLICATE_PAYROLL_RECIPIENT":
                raise
            write_json_line(
                rejected,
                {
                    "resourceId": artifact.resource.resource_id,
                    "entryName": artifact.path.name,
                    "rowNumber": row_number,
                    "reasonCode": error.code,
                    "payloadSha256": hash_content(cells),
                },
            )
            summary["rejected"] += 1
    return summary


def validate_resource(artifact, configuration) -> ValidatedArtifact:
    if hash_file(artifact.path) != artifact.sha256:
        raise IngestionError("ARCHIVE_CHECKSUM_MISMATCH")
    if artifact.path.stat().st_size > configuration.max_download_bytes:
        raise IngestionError("RESOURCE_DOWNLOAD_LIMIT_EXCEEDED")
    rows = parse_payroll_document(artifact.path.read_bytes(), payroll_month(artifact.resource))
    directory = (
        configuration.storage_directory
        / "validated"
        / (f"{artifact.resource.resource_id}-{artifact.sha256}-{ALESP_PARSER_VERSION}")
    )
    create_private_directory(directory)
    records_path, rejected_path = directory / "records.ndjson", directory / "rejected.ndjson"
    with (
        records_path.open("w", encoding="utf-8") as records,
        rejected_path.open("w", encoding="utf-8") as rejected,
    ):
        records_path.chmod(0o600)
        rejected_path.chmod(0o600)
        summary = stage_payroll_rows(artifact, rows, records, rejected)
    return ValidatedArtifact(
        artifact,
        records_path,
        rejected_path,
        hash_file(records_path),
        hash_file(rejected_path),
        configuration.scope_key,
        summary,
        ALESP_PARSER_VERSION,
    )
