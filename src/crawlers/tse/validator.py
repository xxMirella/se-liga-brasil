"""Produce verified staging files and quarantine malformed records before database writes."""

import zipfile
from contextlib import ExitStack
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from crawlers.tse.archive_reader import read_csv_rows, validate_zip_entries
from crawlers.tse.configuration import CrawlerConfiguration
from crawlers.tse.diagnostics import build_record_context
from crawlers.tse.document_storage import stage_document
from crawlers.tse.normalization import normalize_row
from service.identity_resolution.evidence import IdentityEvidenceBuilder, load_identity_key
from service.ingestion.contracts import (
    PARSER_VERSION,
    DownloadedArtifact,
    IngestionError,
    ValidatedArtifact,
)
from service.observability.reporting import emit_event
from storage.files import (
    create_private_directory,
    hash_content,
    hash_file,
    save_json,
    write_json_line,
)
from storage.validation_index import ValidationIndex

DOCUMENT_KINDS = {"government_proposal", "criminal_certificate"}


@dataclass
class ValidationSession:
    artifact: DownloadedArtifact
    configuration: CrawlerConfiguration
    index: ValidationIndex
    records_output: Any
    rejected_output: Any
    identity_builder: Any = None
    summary: dict = field(
        default_factory=lambda: {
            "valid": 0,
            "rejected": 0,
            "duplicates": 0,
            "skipped": 0,
            "entries": 0,
        }
    )

    def reject_record(
        self, error: IngestionError, entry: str, row_number: int | None, raw_payload: dict
    ) -> None:
        self.summary["rejected"] += 1
        write_json_line(
            self.rejected_output,
            {
                "resourceId": self.artifact.resource.resource_id,
                "entryName": entry,
                "rowNumber": row_number,
                "reasonCode": error.code,
                "payloadSha256": hash_content(raw_payload),
                "details": error.details
                | build_record_context(
                    raw_payload, self.artifact.resource.kind, entry, row_number, self.index
                ),
            },
        )

    def accept_record(self, record: dict) -> None:
        if not self.index.register_record(record):
            self.summary["duplicates"] += 1
            return
        write_json_line(self.records_output, record)
        self.summary["valid"] += 1
        if self.artifact.resource.kind == "candidate":
            self.index.register_candidate(record["normalizedData"], record.get("diagnosticContext"))


def is_row_selected(row: dict, session: ValidationSession) -> bool:
    kind = session.artifact.resource.kind
    filtered = session.configuration.ufs or session.configuration.office_codes
    if kind == "complement" and filtered:
        return session.index.has_candidate(row["ANO_ELEICAO"], row["SQ_CANDIDATO"])
    if kind == "asset" and session.configuration.office_codes:
        return session.index.has_candidate(row["ANO_ELEICAO"], row["SQ_CANDIDATO"])
    if (
        kind == "history"
        and session.configuration.office_codes
        and not session.index.has_candidate(row["ANO_ELEICAO_ATUAL"], row["SQ_CANDIDATO_ATUAL"])
    ):
        return False
    if (
        session.configuration.office_codes
        and kind == "candidate"
        and row.get("CD_CARGO") not in session.configuration.office_codes
    ):
        return False
    if not session.configuration.ufs:
        return True
    if kind == "history":
        return (
            row.get("SG_UF_ATUAL") in session.configuration.ufs
            and row.get("SG_UF") in session.configuration.ufs
        )
    return row.get("SG_UF") in session.configuration.ufs


def validate_csv_entry(archive, entry, session: ValidationSession) -> None:
    with archive.open(entry) as source:
        for row_number, row in read_csv_rows(source, session.artifact.resource.kind):
            if row_number % 10000 == 0:
                emit_event("validate_progress", entry_name=entry.filename, rows_scanned=row_number)
            validate_csv_row(row, entry.filename, row_number, session)


def validate_csv_row(row: dict, entry: str, row_number: int, session: ValidationSession) -> None:
    if not is_row_selected(row, session):
        session.summary["skipped"] += 1
        return
    try:
        record = normalize_row(
            row, session.artifact.resource, entry_name=entry, row_number=row_number
        )
        record["diagnosticContext"] = build_record_context(
            row, session.artifact.resource.kind, entry, row_number, session.index
        )
        if session.artifact.resource.kind in {"candidate", "history"} and session.identity_builder:
            record["identityEvidence"] = session.identity_builder.build_evidence(
                row["NM_CANDIDATO"], cpf=row.get("NR_CPF_CANDIDATO")
            )
    except IngestionError as error:
        session.reject_record(error, entry, row_number, row)
        return
    scope = getattr(session.configuration, "allows_identity", None)
    if scope and session.artifact.resource.kind == "candidate" and not scope(record):
        session.summary["skipped"] += 1
        return
    session.accept_record(record)


def validate_document_entry(archive, entry, session: ValidationSession) -> None:
    try:
        with archive.open(entry) as source:
            record = stage_document(source, entry.filename, session.artifact, session.configuration)
    except IngestionError as error:
        session.reject_record(error, entry.filename, None, {"entry_name": entry.filename})
        return
    session.accept_record(record)


def validate_archive_contents(session: ValidationSession) -> None:
    resource = session.artifact.resource
    extension = ".pdf" if resource.kind in DOCUMENT_KINDS else ".csv"
    relevant_entries = 0
    with zipfile.ZipFile(session.artifact.path) as archive:
        validate_zip_entries(archive, session.configuration)
        for entry in archive.infolist():
            session.summary["entries"] += 1
            if not entry.filename.lower().endswith(extension):
                continue
            relevant_entries += 1
            validate_entry = (
                validate_document_entry if resource.kind in DOCUMENT_KINDS else validate_csv_entry
            )
            validate_entry(archive, entry, session)
    if not relevant_entries:
        raise IngestionError("ARCHIVE_FORMAT_CHANGED")


def build_validation_directory(artifact, configuration) -> Path:
    scope_hash = hash_content(configuration.scope_key)[:12]
    name = f"{artifact.resource.resource_id}-{artifact.sha256}-{PARSER_VERSION}-{scope_hash}"
    return configuration.storage_directory / "validated" / name


def validate_resource(
    artifact: DownloadedArtifact, configuration: CrawlerConfiguration, index: ValidationIndex
) -> ValidatedArtifact:
    if hash_file(artifact.path) != artifact.sha256:
        raise IngestionError("ARCHIVE_CHECKSUM_MISMATCH")
    directory = build_validation_directory(artifact, configuration)
    create_private_directory(directory)
    records_path = directory / "records.ndjson"
    rejected_path = directory / "rejected.ndjson"
    index.connection.execute("SAVEPOINT validate_resource")
    try:
        session = write_validation_files(
            artifact, configuration, index, records_path, rejected_path
        )
        index.connection.execute("RELEASE SAVEPOINT validate_resource")
    except Exception:
        index.connection.execute("ROLLBACK TO SAVEPOINT validate_resource")
        index.connection.execute("RELEASE SAVEPOINT validate_resource")
        raise
    validated = ValidatedArtifact(
        artifact,
        records_path,
        rejected_path,
        hash_file(records_path),
        hash_file(rejected_path),
        configuration.scope_key,
        session.summary,
    )
    save_json(directory / "validation.json", serialize_validation(validated))
    return validated


def write_validation_files(artifact, configuration, index, records_path, rejected_path):
    temporary_records = records_path.with_suffix(".tmp")
    temporary_rejected = rejected_path.with_suffix(".tmp")
    try:
        with ExitStack() as stack:
            records = stack.enter_context(temporary_records.open("w", encoding="utf-8"))
            rejected = stack.enter_context(temporary_rejected.open("w", encoding="utf-8"))
            temporary_records.chmod(0o600)
            temporary_rejected.chmod(0o600)
            index.reset_resource()
            builder = IdentityEvidenceBuilder(load_identity_key())
            session = ValidationSession(artifact, configuration, index, records, rejected, builder)
            validate_archive_contents(session)
        temporary_records.replace(records_path)
        temporary_rejected.replace(rejected_path)
        return session
    finally:
        temporary_records.unlink(missing_ok=True)
        temporary_rejected.unlink(missing_ok=True)


# Public compatibility imports; staging manifests are source-independent.
from storage.staging import deserialize_validation, serialize_validation  # noqa: E402, F401
