"""Local change detection gates consolidation; timestamps alone do not create new facts."""

import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from service.analytical_datasets import DatasetPartition
from service.analytical_datasets.public_voting_timeline import project_public_voting_timeline


class VotingChangeIndex:
    def __init__(self, path, *, parser_version=None):
        self.parser_version = parser_version
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.connection = sqlite3.connect(path)
        path.chmod(0o600)
        self.connection.execute("PRAGMA busy_timeout=5000")
        self.connection.execute("""CREATE TABLE IF NOT EXISTS fact (
          source TEXT,person_id TEXT,voting_id TEXT,digest TEXT,observed_at TEXT,occurred_on TEXT,
          PRIMARY KEY(source,person_id,voting_id))""")
        self.connection.execute("""CREATE TABLE IF NOT EXISTS retirement (
          source TEXT,voting_id TEXT,occurred_on TEXT,observed_at TEXT,
          PRIMARY KEY(source,voting_id,occurred_on))""")

        columns = {row[1] for row in self.connection.execute("PRAGMA table_info(fact)")}
        if "parser_version" not in columns:
            self.connection.execute("ALTER TABLE fact ADD COLUMN parser_version TEXT")

    def close(self):
        self.connection.close()

    def inspect_record(self, record):
        public = project_public_voting_timeline(
            {key: value for key, value in record.items() if key != "source_observed_at"},
            DatasetPartition(record["institution_code"], int(record["occurred_on"][:4])),
        )
        digest = hashlib.sha256(json.dumps(public, sort_keys=True).encode()).hexdigest()
        key = record["institution_code"], record["person_id"], record["voting_id"]
        observed = normalize_observation(record["source_observed_at"])
        old = self.connection.execute(
            "SELECT digest,observed_at,occurred_on,parser_version FROM fact "
            "WHERE source=? AND person_id=? AND voting_id=?",
            key,
        ).fetchone()
        if old and (old[0] == digest or observed < old[1]):
            return None
        revised_parser = self.parser_version is not None and old and old[3] != self.parser_version
        if old and observed == old[1] and not revised_parser:
            raise ValueError("Conflicting voting facts with the same source observation")
        previous_day = old[2] if old and old[2] != record["occurred_on"] else None
        return (*key, digest, observed, record["occurred_on"], self.parser_version), previous_day

    def inspect_retirement(self, source, retirement):
        key = source, retirement["voting_id"], retirement["occurred_on"]
        observed = normalize_observation(retirement["source_observed_at"])
        old = self.connection.execute(
            "SELECT observed_at FROM retirement WHERE source=? AND voting_id=? AND occurred_on=?",
            key,
        ).fetchone()
        return None if old and observed <= old[0] else (*key, observed)

    def commit_changes(self, facts, retirements):
        with self.connection:
            self.connection.executemany("INSERT OR REPLACE INTO fact VALUES(?,?,?,?,?,?,?)", facts)
            self.connection.executemany(
                "INSERT OR REPLACE INTO retirement VALUES(?,?,?,?)", retirements
            )


def normalize_observation(value):
    observation = datetime.fromisoformat(value)
    if observation.tzinfo is None:
        raise ValueError("Source observation requires a timezone")
    return observation.astimezone(UTC).isoformat(timespec="microseconds")
