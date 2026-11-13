"""Shared vocabulary of the archive: targets, file naming and errors."""

import re
from dataclasses import dataclass, field

ARCHIVE_FORMAT_VERSION = 1
MANIFEST_FILE_NAME = "manifest.json"
VERIFICATION_FILE_NAME = "verification.json"
IDENTIFIER_PATTERN = re.compile(r"^[a-z_][a-z0-9_]*$")


class ArchiveError(RuntimeError):
    """The archive cannot be produced, verified or restored safely."""


@dataclass(frozen=True)
class ArchiveTarget:
    """One file of the archive: a whole table or a named, fixed slice of it."""

    schema: str
    table: str
    slice_name: str | None = None
    slice_predicate_sql: str | None = None
    verify_source_record_payload_hash: bool = False
    description: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def qualified_name(self) -> str:
        return f"{self.schema}.{self.table}"

    @property
    def file_name(self) -> str:
        suffix = f"@{self.slice_name}" if self.slice_name else ""
        return f"{self.schema}.{self.table}{suffix}.ndjson.gz"


def require_identifier(value: str) -> str:
    if not IDENTIFIER_PATTERN.match(value):
        raise ArchiveError(f"INVALID_IDENTIFIER:{value}")
    return value
