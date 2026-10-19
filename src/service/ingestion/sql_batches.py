"""Set-based reconciliation; SQL calls scale with batches, never individual records."""

import re

from database.operations import read_sql_file

TEMP_BATCH_SQL = """
CREATE TEMP TABLE ingestion_batch (
 kind text,external_key text,content_sha256 text,normalized_data jsonb,
 source_generated_at timestamptz,entry_name text,row_number integer,
 source_record_id bigint,entity_id bigint,classification text,identity_evidence jsonb,
 diagnostic_context jsonb
) ON COMMIT DROP
"""


class SqlBatchWriter:
    def __init__(self, connection) -> None:
        self.connection = connection
        self.sql_cache: dict[str, list[str]] = {}

    def execute_statements(self, filename: str, parameters: dict) -> None:
        if filename not in self.sql_cache:
            sql = read_sql_file(f"ingestion/{filename}.sql")
            sql = re.sub(r"(?m)^\s*--.*$", "", sql)
            self.sql_cache[filename] = [
                statement.strip() for statement in sql.split(";") if statement.strip()
            ]
        with self.connection.pipeline():
            for statement in self.sql_cache[filename]:
                self.connection.execute(statement, parameters)

    def summarize_batch(self) -> dict[str, int]:
        rows = self.connection.execute("""
            SELECT classification,count(*)::int AS count 
                FROM ingestion_batch GROUP BY classification
        """).fetchall()
        return {row["classification"]: row["count"] for row in rows}
