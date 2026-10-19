"""Validate ZIP structure and stream strict Latin-1 CSV records."""

import csv
import io
import re
import zipfile
from collections.abc import Iterator
from pathlib import PurePosixPath

from crawlers.tse.configuration import CrawlerConfiguration
from crawlers.tse.normalization import REQUIRED_HEADERS
from service.ingestion.contracts import IngestionError

MAX_ARCHIVE_ENTRIES = 100000
MAX_CSV_FIELD_BYTES = 1024 * 1024


def validate_zip_entries(archive: zipfile.ZipFile, configuration: CrawlerConfiguration) -> None:
    entries = archive.infolist()
    if len(entries) > MAX_ARCHIVE_ENTRIES:
        raise IngestionError("ARCHIVE_ENTRY_LIMIT_EXCEEDED")
    expanded_bytes = sum(entry.file_size for entry in entries)
    if expanded_bytes > configuration.max_archive_expanded_bytes:
        raise IngestionError("ARCHIVE_EXPANSION_LIMIT_EXCEEDED")
    for entry in entries:
        validate_zip_entry(entry, configuration)


def validate_zip_entry(entry: zipfile.ZipInfo, configuration: CrawlerConfiguration) -> None:
    path = PurePosixPath(entry.filename)
    if path.is_absolute() or ".." in path.parts or "\\" in entry.filename or entry.flag_bits & 1:
        raise IngestionError("UNSAFE_ARCHIVE_ENTRY")
    if entry.file_size > configuration.max_entry_bytes:
        raise IngestionError("ARCHIVE_ENTRY_TOO_LARGE")
    file_type = (entry.external_attr >> 16) & 0o170000
    if file_type == 0o120000:
        raise IngestionError("ARCHIVE_SYMLINK_REJECTED")


def validate_csv_headers(headers: list[str] | None, kind: str) -> None:
    if not headers or len(headers) != len(set(headers)):
        raise IngestionError("INVALID_CSV_HEADER")
    missing = REQUIRED_HEADERS[kind] - set(headers)
    if missing:
        raise IngestionError("CSV_SCHEMA_CHANGED", {"missing_headers": sorted(missing)})
    if any(not re.fullmatch(r"[A-Z][A-Z0-9_]*", header) for header in headers):
        raise IngestionError("INVALID_CSV_HEADER")


def read_csv_rows(source, kind: str) -> Iterator[tuple[int, dict]]:
    csv.field_size_limit(MAX_CSV_FIELD_BYTES)
    with io.TextIOWrapper(source, encoding="latin1", newline="") as text_source:
        reader = csv.DictReader(text_source, delimiter=";", strict=True)
        validate_csv_headers(reader.fieldnames, kind)
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise IngestionError("CSV_COLUMN_COUNT_MISMATCH", {"row_number": reader.line_num})
            yield reader.line_num, row
