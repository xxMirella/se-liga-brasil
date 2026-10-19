"""Disk-backed indexes keep duplicate detection and scope filtering bounded in RAM."""

import json
import sqlite3
from pathlib import Path

from service.ingestion.contracts import IngestionError


class ValidationIndex:
    def __init__(self, path: Path) -> None:
        self.connection = sqlite3.connect(path)
        self.connection.execute("PRAGMA cache_size=-4096")
        self.connection.execute("CREATE TABLE IF NOT EXISTS candidate_scope (key TEXT PRIMARY KEY)")
        columns = {row[1] for row in self.connection.execute("PRAGMA table_info(candidate_scope)")}
        if "context" not in columns:
            self.connection.execute("ALTER TABLE candidate_scope ADD COLUMN context TEXT")
        self.connection.execute("CREATE TABLE IF NOT EXISTS seen (key TEXT PRIMARY KEY, hash TEXT)")

    def reset_resource(self) -> None:
        self.connection.execute("DELETE FROM seen")

    def register_record(self, record: dict) -> bool:
        existing = self.connection.execute(
            "SELECT hash FROM seen WHERE key=?", (record["externalKey"],)
        ).fetchone()
        if existing:
            if existing[0] != record["contentSha256"]:
                raise IngestionError("CONFLICTING_DUPLICATE_KEY")
            return False
        self.connection.execute(
            "INSERT INTO seen VALUES (?,?)", (record["externalKey"], record["contentSha256"])
        )
        return True

    def register_candidate(self, data: dict, context: dict | None = None) -> None:
        self.connection.execute(
            "INSERT INTO candidate_scope(key,context) VALUES (?,?) "
            "ON CONFLICT(key) DO UPDATE SET context=excluded.context",
            (f"{data['electionYear']}:{data['candidateSequence']}", json.dumps(context or {})),
        )

    def has_candidate(self, year: str, sequence: str) -> bool:
        return (
            self.connection.execute(
                "SELECT 1 FROM candidate_scope WHERE key=?", (f"{year}:{sequence}",)
            ).fetchone()
            is not None
        )

    def candidate_context(self, year, sequence) -> dict:
        row = self.connection.execute(
            "SELECT context FROM candidate_scope WHERE key=?", (f"{year}:{sequence}",)
        ).fetchone()
        return json.loads(row[0]) if row and row[0] else {}

    def close(self) -> None:
        self.connection.close()
