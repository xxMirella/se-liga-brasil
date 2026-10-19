"""Transport-independent ingestion contracts."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PARSER_VERSION = "tse-python-v5"
RESOURCE_KINDS = (
    "candidate",
    "history",
    "complement",
    "asset",
    "government_proposal",
    "criminal_certificate",
)


class IngestionError(Exception):
    """A safe error code and non-sensitive context suitable for audit logs."""

    def __init__(self, code: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.details = details or {}


@dataclass(frozen=True)
class Resource:
    resource_id: str
    name: str
    url: str
    kind: str
    year: int
    dataset: str
    uf: str | None = None
    file_suffix: str = ".zip"


@dataclass(frozen=True)
class DownloadedArtifact:
    resource: Resource
    path: Path
    sha256: str
    fetched_at: str
    bytes_downloaded: int
    acquisition_status: str = "downloaded"


@dataclass(frozen=True)
class ValidatedArtifact:
    artifact: DownloadedArtifact
    records_path: Path
    rejected_path: Path
    records_sha256: str
    rejected_sha256: str
    scope_key: str
    summary: dict[str, int]
    parser_version: str = PARSER_VERSION


@dataclass
class DownloadBudget:
    bytes_used: int = 0


@dataclass
class IngestionSummary:
    new: int = 0
    changed: int = 0
    unchanged: int = 0
    stale: int = 0
    rejected: int = 0
    skipped_artifact: bool = False
    classifications: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class SourceDescriptor:
    code: str
    publisher: str
    official_url: str
    acquisition_method: str = "download"
