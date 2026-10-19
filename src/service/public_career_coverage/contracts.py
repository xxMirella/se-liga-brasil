"""Explicit expectations and acquisition proofs; event counts are not coverage proofs."""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class CoverageScope:
    person_id: str
    institution: str
    domain: str
    starts_on: date
    ends_before: date
    source: str
    partition: str
    applicability: str = "applicable"

    def __post_init__(self):
        if self.ends_before <= self.starts_on:
            raise ValueError("Coverage interval must be nonempty and end-exclusive")
        if self.applicability not in {"applicable", "unknown", "not_applicable"}:
            raise ValueError("Unsupported applicability")


@dataclass(frozen=True)
class CoverageReceipt:
    scope: CoverageScope
    checked_on: date
    identity_verified: bool
    enumeration_complete: bool
    source_period_complete: bool
    artifact_verified: bool
    status: str = "available"
    artifact_sha256: str | None = None
    parser_version: str | None = None
    scope_verified: bool = False

    def __post_init__(self):
        if self.status not in {"available", "unavailable"}:
            raise ValueError("Unsupported acquisition status")


@dataclass(frozen=True)
class AcquisitionResource:
    source: str
    institution: str
    domain: str
    partition: str
    person_ids: tuple[str, ...]
    prefer_local: bool = True
    expected_scopes: tuple[CoverageScope, ...] = ()
