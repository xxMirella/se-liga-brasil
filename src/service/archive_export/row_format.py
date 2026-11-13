"""One archive line: {"row_sha256":"<hex>","key":[<primary key>],"row":{<whole row>}}.

`row` is the exact text of PostgreSQL `to_jsonb(row)::text` (lossless for uuid, timestamptz,
numeric, arrays, jsonb and bytea) and `row_sha256` is the SHA-256 of that text in UTF-8, so the
database can recompute it with `sha256(convert_to(to_jsonb(t)::text,'UTF8'))`.
"""

import hashlib
from typing import NamedTuple

from service.archive_export.contracts import ArchiveError

LINE_PREFIX = '{"row_sha256":"'
KEY_MARKER = '","key":'
ROW_MARKER = ',"row":'
HASH_LENGTH = 64


class ArchivedRow(NamedTuple):
    row_sha256: str
    key_text: str
    row_text: str


def hash_row_text(row_text: str) -> str:
    return hashlib.sha256(row_text.encode("utf-8")).hexdigest()


def encode_line(key_text: str, row_text: str) -> tuple[str, bytes]:
    """The row hash and the encoded line."""
    digest = hash_row_text(row_text)
    line = f"{LINE_PREFIX}{digest}{KEY_MARKER}{key_text}{ROW_MARKER}{row_text}}}\n"
    return digest, line.encode("utf-8")


def decode_line(line: str) -> ArchivedRow:
    start = len(LINE_PREFIX)
    key_start = start + HASH_LENGTH + len(KEY_MARKER)
    if not line.startswith(LINE_PREFIX) or line[start + HASH_LENGTH : key_start] != KEY_MARKER:
        raise ArchiveError("MALFORMED_ARCHIVE_LINE")
    row_marker_at = line.find(ROW_MARKER, key_start)
    if row_marker_at < 0 or not line.rstrip("\n").endswith("}"):
        raise ArchiveError("MALFORMED_ARCHIVE_LINE")
    row_text = line[row_marker_at + len(ROW_MARKER) : len(line.rstrip("\n")) - 1]
    return ArchivedRow(line[start : start + HASH_LENGTH], line[key_start:row_marker_at], row_text)


def checked_row(line: str) -> ArchivedRow:
    """Decode a line and fail when its stored hash does not match its content."""
    row = decode_line(line)
    if hash_row_text(row.row_text) != row.row_sha256:
        raise ArchiveError("ARCHIVE_ROW_HASH_MISMATCH:" + row.key_text)
    return row
