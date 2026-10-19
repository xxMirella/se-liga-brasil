"""Public API for source-agnostic identity and change checks."""

from .existence import DataExistenceService, RecordIdentity, RecordSnapshot, RecordState

__all__ = ["DataExistenceService", "RecordIdentity", "RecordSnapshot", "RecordState"]
