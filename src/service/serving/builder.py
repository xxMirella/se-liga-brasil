"""Atomic dataset builder: build in staging, then swap and record the release in one transaction.

Readers only ever see the previous complete table or the new complete table. Any failure rolls
back the whole transaction, so nothing that is served changes. The slow work (populate, indexes)
happens before the exclusive lock; the lock is held only for the drop/rename/release write.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from itertools import islice

from service.serving.release import RELEASE_TABLE, SERVING_SCHEMA, DatasetRelease

NAME_PATTERN = re.compile(r"[a-z][a-z0-9_]{0,40}")
BATCH_SIZE = 1000
SWAP_LOCK_TIMEOUT = "10s"


@dataclass(frozen=True)
class DatasetSpec:
    """Definition of one serving table.

    `columns_ddl` and `indexes` are trusted code constants (never user input). Indexes are the
    tail of `CREATE INDEX ON <table> ...`, e.g. "(party_sort_key, display_name)" or
    "USING gin (uf)"; the database chooses unique index names so builds never collide.
    Provide either `rows` (+ `columns`) or `insert_sql` containing a `{table}` placeholder.
    """

    name: str
    columns_ddl: str
    indexes: tuple[str, ...] = ()
    columns: tuple[str, ...] = ()
    rows: Iterable[tuple] | None = None
    insert_sql: str | None = None


def build_dataset(connection, spec: DatasetSpec, as_of: date) -> DatasetRelease:
    _validate(spec)
    live, staging = _qualified(spec.name), _qualified(f"{spec.name}__staging")
    with connection.transaction():
        connection.execute(
            "SELECT pg_advisory_xact_lock(hashtext(%s))", (f"{SERVING_SCHEMA}:{spec.name}",)
        )
        _build_staging(connection, spec, staging)
        row_count, version = _measure(connection, staging)
        _swap(connection, live, staging, spec.name)
        _record_release(connection, spec.name, version, as_of, row_count)
        return _read_release(connection, spec.name)


def _validate(spec: DatasetSpec) -> None:
    if not NAME_PATTERN.fullmatch(spec.name) or spec.name.endswith("__staging"):
        raise ValueError("SERVING_DATASET_NAME_INVALID")
    if (spec.rows is None) == (spec.insert_sql is None):
        raise ValueError("SERVING_DATASET_NEEDS_EXACTLY_ONE_SOURCE")
    if spec.rows is not None and not spec.columns:
        raise ValueError("SERVING_DATASET_ROWS_NEED_COLUMNS")


def _qualified(table_name: str) -> str:
    return f"{SERVING_SCHEMA}.{table_name}"


def _build_staging(connection, spec: DatasetSpec, staging: str) -> None:
    connection.execute(f"DROP TABLE IF EXISTS {staging}")
    connection.execute(f"CREATE TABLE {staging} ({spec.columns_ddl})")
    connection.execute(f"ALTER TABLE {staging} ENABLE ROW LEVEL SECURITY")
    connection.execute(f"REVOKE ALL ON {staging} FROM PUBLIC")
    if spec.insert_sql is not None:
        connection.execute(spec.insert_sql.format(table=staging))
    else:
        _insert_rows(connection, staging, spec.columns, spec.rows)
    for definition in spec.indexes:
        connection.execute(f"CREATE INDEX ON {staging} {definition}")
    connection.execute(f"ANALYZE {staging}")


def _insert_rows(connection, staging, columns, rows) -> None:
    placeholders = ",".join(["%s"] * len(columns))
    statement = f"INSERT INTO {staging}({','.join(columns)}) VALUES({placeholders})"
    iterator = iter(rows)
    with connection.cursor() as cursor:
        while batch := list(islice(iterator, BATCH_SIZE)):
            cursor.executemany(statement, batch)


def _measure(connection, staging: str) -> tuple[int, str]:
    """Row count and a content hash that is stable across identical rebuilds."""
    row = connection.execute(
        f"SELECT count(*)::int AS row_count,"
        f" md5(coalesce(string_agg(md5(t::text),'' ORDER BY md5(t::text)),'')) AS version"
        f" FROM {staging} t"
    ).fetchone()
    return row["row_count"], row["version"]


def _swap(connection, live: str, staging: str, name: str) -> None:
    connection.execute(f"SET LOCAL lock_timeout='{SWAP_LOCK_TIMEOUT}'")
    connection.execute(f"DROP TABLE IF EXISTS {live}")
    connection.execute(f"ALTER TABLE {staging} RENAME TO {name}")


def _record_release(connection, name, version, as_of, row_count) -> None:
    connection.execute(
        f"INSERT INTO {RELEASE_TABLE}(name,version,built_at,as_of,row_count)"
        " VALUES(%s,%s,clock_timestamp(),%s,%s)"
        " ON CONFLICT(name) DO UPDATE SET version=EXCLUDED.version,"
        " built_at=EXCLUDED.built_at,as_of=EXCLUDED.as_of,row_count=EXCLUDED.row_count",
        (name, version, as_of, row_count),
    )


def _read_release(connection, name) -> DatasetRelease:
    row = connection.execute(
        f"SELECT name,version,built_at,as_of,row_count FROM {RELEASE_TABLE} WHERE name=%s",
        (name,),
    ).fetchone()
    return DatasetRelease(**row)
