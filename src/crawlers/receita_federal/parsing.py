"""Stream semicolon CP1252 CSV directly from ZIP, without extracting originals."""

import csv
from io import TextIOWrapper
from zipfile import ZipFile

from service.ingestion.contracts import IngestionError

FIELD_COUNTS = {"companies": 7, "establishments": 30, "partners": 11}


def validate_members(archive, configuration):
    members = archive.infolist()
    if len(members) > configuration.max_members_per_resource:
        raise IngestionError("CNPJ_ZIP_MEMBER_LIMIT_EXCEEDED")
    if any(member.is_dir() or member.flag_bits & 1 for member in members):
        raise IngestionError("CNPJ_UNSUPPORTED_ZIP_MEMBER")
    if sum(member.file_size for member in members) > configuration.max_uncompressed_bytes:
        raise IngestionError("CNPJ_UNCOMPRESSED_LIMIT_EXCEEDED")
    return members


def iter_partition_rows(path, kind, configuration):
    expected_fields = FIELD_COUNTS.get(kind)
    if expected_fields is None:
        raise IngestionError("CNPJ_UNSUPPORTED_KIND")
    count = 0
    with ZipFile(path) as archive:
        for member in validate_members(archive, configuration):
            with archive.open(member) as binary:
                text = TextIOWrapper(binary, encoding="cp1252", newline="")
                for row in csv.reader(text, delimiter=";", strict=True):
                    count += 1
                    if count > configuration.max_records_per_resource:
                        raise IngestionError("CNPJ_RECORD_LIMIT_EXCEEDED")
                    if len(row) != expected_fields:
                        raise IngestionError("CNPJ_LAYOUT_CHANGED")
                    yield row
