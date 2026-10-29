"""Published per-territory history: read by key with a version check, written when publishing."""

import psycopg.errors

from service.political_dashboard_dataset.history import (
    dataset_version,
    decode_history_base64,
    expand_history_row,
    sort_key,
)

HISTORY_TABLE = "se_liga_brasil.political_dashboard_history"

UPSERT_HISTORY = f"""
INSERT INTO {HISTORY_TABLE}
 (territory_code,schema_version,content_sha256,row_count,uncompressed_bytes,payload_zlib)
SELECT * FROM unnest(%s::text[],%s::text[],%s::text[],%s::integer[],%s::integer[],%s::bytea[])
ON CONFLICT(territory_code) DO UPDATE SET
 schema_version=excluded.schema_version,content_sha256=excluded.content_sha256,
 row_count=excluded.row_count,uncompressed_bytes=excluded.uncompressed_bytes,
 payload_zlib=excluded.payload_zlib,published_at=now()
WHERE {HISTORY_TABLE}.content_sha256<>excluded.content_sha256
"""

# One statement, one PostgreSQL snapshot: the selected year plus the history rows whose
# version differs from the one the caller already holds (the payload is sent only then).
SNAPSHOT_QUERY = f"""
WITH known AS (
 SELECT * FROM unnest(%s::text[],%s::text[]) AS k(territory_code,content_sha256)
), selected AS (
 SELECT content_sha256,payload FROM se_liga_brasil.political_dashboard_annual
 WHERE year=%s AND territory_code=ANY(%s) ORDER BY territory_code,institution_code LIMIT 32
)
SELECT coalesce((SELECT jsonb_agg(jsonb_build_object(
  'payload',payload,'content_sha256',content_sha256)) FROM selected),'[]'::jsonb) AS partitions,
 coalesce((SELECT jsonb_agg(jsonb_build_object(
  'territory_code',h.territory_code,'content_sha256',h.content_sha256,
  'published_at',h.published_at,
  'payload_base64',CASE WHEN k.content_sha256 IS DISTINCT FROM h.content_sha256
   THEN translate(encode(h.payload_zlib,'base64'),E'\\n','') END))
  FROM {HISTORY_TABLE} h LEFT JOIN known k USING(territory_code)
  WHERE h.territory_code=ANY(%s)),'[]'::jsonb) AS histories
"""


class DashboardHistoryTable:
    def __init__(self, connection):
        self.connection = connection

    def is_available(self):
        return self.connection.execute(
            f"SELECT to_regclass('{HISTORY_TABLE}') IS NOT NULL AS exists"
        ).fetchone()["exists"]

    def upsert(self, entries):
        """Insert or replace only territories whose content digest changed; returns that count."""
        if not entries:
            return 0
        columns = (
            "territory_code",
            "schema_version",
            "content_sha256",
            "row_count",
            "uncompressed_bytes",
            "payload_zlib",
        )
        return self.connection.execute(
            UPSERT_HISTORY, tuple([entry[column] for entry in entries] for column in columns)
        ).rowcount

    def fetch_digests(self, territories):
        rows = self.connection.execute(
            f"SELECT territory_code,content_sha256 FROM {HISTORY_TABLE} "
            "WHERE territory_code=ANY(%s)",
            (list(territories),),
        ).fetchall()
        return {row["territory_code"]: row["content_sha256"] for row in rows}

    def list_annual_territories(self):
        return [
            row["territory_code"]
            for row in self.connection.execute(
                "SELECT DISTINCT territory_code FROM se_liga_brasil.political_dashboard_annual "
                "ORDER BY territory_code"
            ).fetchall()
        ]


class PublishedHistoryReader:
    """Reads a territory history once per published version, not once per request."""

    def __init__(self, connection, cache):
        self.connection, self.cache = connection, cache

    def fetch_snapshot(self, year, territories):
        """Rows for the selected territories, or None when the caller must fall back.

        The fallback applies while the table (or any territory row) is not published yet.
        A cached copy evicted between the version check and its use is simply re-read once.
        """
        territories = sorted(set(territories))
        with self.cache.lock_for(tuple(territories)):
            for _ in range(2):
                snapshot = self.query(year, territories)
                if snapshot is None or {
                    item["territory_code"] for item in snapshot["histories"]
                } != set(territories):
                    return None
                if self.is_cached(snapshot):
                    return snapshot
            return None

    def query(self, year, territories):
        known = {t: entry.version for t in territories if (entry := self.cache.get(t))}
        try:
            row = self.connection.execute(
                SNAPSHOT_QUERY,
                (list(known), list(known.values()), year, territories, territories),
            ).fetchone()
        except psycopg.errors.UndefinedTable:
            return None
        for item in row["histories"]:
            if item["payload_base64"] is not None:
                rows = decode_history_base64(item["payload_base64"])["rows"]
                self.cache.store(item["territory_code"], item["content_sha256"], rows)
        return row

    def is_cached(self, snapshot):
        return all(
            (entry := self.cache.get(item["territory_code"])) is not None
            and entry.version == item["content_sha256"]
            for item in snapshot["histories"]
        )


def assemble_snapshot(snapshot, cache):
    """Flatten the cached territories into the row list the aggregation consumes."""
    histories = snapshot["histories"]
    rows = [
        expand_history_row(stored)
        for item in histories
        for stored in cache.get(item["territory_code"]).rows()
    ]
    rows.sort(key=sort_key)
    return {
        "partitions": [
            {"payload": item["payload"], "content_sha256": item["content_sha256"]}
            for item in snapshot["partitions"]
        ],
        "history": rows,
        "dataset_version": dataset_version(
            [item["content_sha256"] for item in histories],
            [item["content_sha256"] for item in snapshot["partitions"]],
        ),
        "dataset_generated_at": max((item["published_at"] for item in histories), default=None),
    }
