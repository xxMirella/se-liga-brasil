"""PostgreSQL adapter for generic existence checks; identifiers are always parameters."""

from dataclasses import asdict

from psycopg.types.json import Jsonb

from service.data_validation.existence import RecordIdentity, StoredRecord


class PostgresRecordLookup:
    def __init__(self, connection) -> None:
        self.connection = connection

    def fetch_existing_records(
        self, identities: list[RecordIdentity]
    ) -> dict[RecordIdentity, StoredRecord]:
        if not identities:
            return {}
        rows = self.connection.execute(
            """
            SELECT source.code AS source_code,entity.entity_kind AS data_type,
              entity.external_key,entity.content_sha256,entity.source_generated_at
            FROM jsonb_to_recordset(%s::jsonb)
              AS requested(source_code text,data_type text,external_key text)
            JOIN se_liga_brasil.source source ON source.code=requested.source_code
            JOIN se_liga_brasil.ingestion_entity entity ON entity.source_id=source.id
              AND entity.entity_kind=requested.data_type
              AND entity.external_key=requested.external_key
        """,
            (Jsonb([asdict(identity) for identity in identities]),),
        ).fetchall()
        return {
            RecordIdentity(row["source_code"], row["data_type"], row["external_key"]): StoredRecord(
                row["content_sha256"], row["source_generated_at"]
            )
            for row in rows
        }
