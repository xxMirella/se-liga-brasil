"""Export -> verify -> migration 0028 -> restore, end to end, in a throwaway schema.

Requires TEST_DATABASE_URL pointing at a disposable PostgreSQL. All data is synthetic.
"""

import gzip
import json
import os
import re
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from psycopg import errors

from database.operations import PROJECT_ROOT, read_sql_file, strip_transaction_wrapper
from service.archive_export.contracts import ArchiveError
from service.archive_export.exporter import export_archive
from service.archive_export.restorer import restore_archive
from service.archive_export.snapshot_connection import read_only_snapshot
from service.archive_export.targets import removal_targets, snapshot_targets
from service.archive_export.verifier import verify_archive
from storage.files import hash_content

pytestmark = pytest.mark.integration
RECORDS_PER_TYPE = 1500
NULLED_TYPES = {
    ("alesp", "alesp_propositions"),
    ("alesp", "alesp_attendance"),
    ("tse", "asset"),
    ("tse", "complement"),
}
KEPT_TYPES = {("tse", "candidate"), ("tse", "history")}
PROBE_DDL = """
CREATE TABLE {schema}.archive_type_probe (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, owner uuid NOT NULL,
 seen_at timestamptz NOT NULL, born date, tags text[] NOT NULL, blob bytea,
 amount numeric(20,6), ratio double precision,
 document jsonb, note text, flag boolean, doubled integer GENERATED ALWAYS AS (id * 2) STORED);
CREATE TABLE {schema}.archive_no_key_probe (label text, amount numeric);
"""


def long_text(seed: int) -> str:
    return f"Proposição nº {seed}: ação São João, çãõ — “aspas” \\ \n\t 日本語 😀 " * 8


def synthetic_payload(kind: str, number: int) -> dict:
    return {
        "kind": kind,
        "number": number,
        "title": long_text(number),
        "ratio": number / 7,
        "amount": 1234.5,
        "nested": {"list": [number, None, True, "x" * 50], "emptyObject": {}},
    }


@pytest.fixture
def archive_database():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL for isolated SQL tests")
    import psycopg
    from psycopg.rows import dict_row

    schema = f"se_liga_brasil_test_{uuid4().hex[:12]}"
    connection = psycopg.connect(url, autocommit=True, row_factory=dict_row, prepare_threshold=None)
    try:
        files = ["schema.sql"] + [
            f"migrations/{path.name}"
            for path in sorted((PROJECT_ROOT / "db/migrations").glob("*.sql"))
            if path.name >= "0003"
        ]
        for name in files:
            connection.execute(
                strip_transaction_wrapper(read_sql_file(name)).replace("se_liga_brasil", schema)
            )
        connection.execute(PROBE_DDL.format(schema=schema))
        yield connection, schema
    finally:
        if connection.info.transaction_status:
            connection.rollback()
        connection.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        connection.execute(f'DROP SCHEMA IF EXISTS "{schema}_serving" CASCADE')
        connection.close()


def seed_records(connection, schema):
    for code in ("alesp", "tse"):
        connection.execute(
            f"INSERT INTO {schema}.source(code,publisher,official_url,acquisition_method) "
            "VALUES(%s,'Fictícia','https://example.test','api')",
            (code,),
        )
    ids = {r["code"]: r["id"] for r in connection.execute(f"SELECT id,code FROM {schema}.source")}
    rows = []
    for source_code, kind in sorted(NULLED_TYPES | KEPT_TYPES):
        for number in range(RECORDS_PER_TYPE):
            payload = synthetic_payload(kind, number)
            rows.append(
                (
                    ids[source_code],
                    f"{kind}:{number}",
                    "https://example.test/x",
                    hash_content(payload),
                    json.dumps(payload),
                    None if number % 10 == 0 else "data/archive/synthetic.zip",
                )
            )
    with connection.cursor() as cursor:
        cursor.executemany(
            f"INSERT INTO {schema}.source_record(source_id,external_key,source_url,content_sha256,"
            "payload,storage_reference) VALUES(%s,%s,%s,%s,%s::jsonb,%s)",
            rows,
        )


def seed_probe_tables(connection, schema):
    for number in range(3000):
        connection.execute(
            f"INSERT INTO {schema}.archive_type_probe(owner,seen_at,born,tags,blob,amount,ratio,"
            "document,note,flag) VALUES(%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)",
            (
                uuid4(),
                datetime(2026, 1, 1, 12, number % 60, tzinfo=UTC),
                "1980-05-17",
                ["a", "ção", "{x,y}", 'q"uote'],
                bytes(range(256)) if number % 2 else None,
                Decimal("12345678901234.123456"),
                0.1 + number / 3,
                json.dumps({"n": number, "txt": long_text(number)}),
                None if number % 3 else long_text(number),
                number % 2 == 0,
            ),
        )
    connection.execute(
        f"INSERT INTO {schema}.archive_no_key_probe VALUES('a',1),('a',1),(NULL,NULL)"
    )


def table_fingerprint(connection, schema, table, order="1"):
    rows = connection.execute(
        f"SELECT to_jsonb(t)::text AS value FROM {schema}.{table} t ORDER BY 1"
    ).fetchall()
    return [row["value"] for row in rows]


def acknowledge_and_migrate(connection, schema):
    sql_text = (
        PROJECT_ROOT / "db/migrations/0028_null_unread_source_record_payload.sql"
    ).read_text()
    # psql sends statements one by one; a multi-statement string would be one implicit transaction
    # and COMMIT inside the DO block would be refused.
    settings, block = sql_text.replace("se_liga_brasil", schema).split("DO $$", 1)
    for statement in re.findall(r"^SET [^;]+;", settings, flags=re.MULTILINE):
        connection.execute(statement)
    connection.execute("DO $$" + block)


def count_where(connection, schema, condition):
    return connection.execute(
        f"SELECT count(*) AS n FROM {schema}.source_record WHERE {condition}"
    ).fetchone()["n"]


def export_snapshot_and_verify(connection, schema, archive):
    targets = snapshot_targets(connection, schema, f"{schema}_serving")
    by_file = {
        e["file"]: e for e in export_archive(connection, targets, archive, "snapshot")["files"]
    }
    assert by_file[f"{schema}.source_record.ndjson.gz"]["row_count"] == 6 * RECORDS_PER_TYPE
    assert by_file[f"{schema}.archive_type_probe.ndjson.gz"]["row_count"] == 3000
    assert by_file[f"{schema}.archive_no_key_probe.ndjson.gz"]["row_count"] == 3
    assert "doubled" not in by_file[f"{schema}.archive_type_probe.ndjson.gz"]["columns"]
    slice_entry = by_file[f"{schema}.source_record@payload_without_readers.ndjson.gz"]
    assert slice_entry["row_count"] == 4 * RECORDS_PER_TYPE
    report = verify_archive(connection, archive)
    assert report["all_files_ok"], report
    return slice_entry


def apply_migration_0028(connection, schema):
    """Skipped without acknowledgement; then it nulls only the unread types, in batches."""
    acknowledge_and_migrate(connection, schema)
    assert nulled_count(connection, schema) == 0
    connection.execute(f"SET {schema}.verified_archive_manifest_sha256 = '{'a' * 64}'")
    acknowledge_and_migrate(connection, schema)
    assert nulled_count(connection, schema) == 4 * RECORDS_PER_TYPE * 9 // 10
    assert (
        count_where(
            connection,
            schema,
            "payload IS NULL AND split_part(external_key,':',1) IN ('candidate','history')",
        )
        == 0
    )
    # rows without storage_reference keep their payload (the CHECK constraint stays true)
    assert count_where(connection, schema, "payload IS NOT NULL AND storage_reference IS NULL") == (
        6 * RECORDS_PER_TYPE // 10
    )


def roll_back_payloads(connection, schema, archive, slice_entry, before_records):
    options = {"mode": "fill-null-columns", "columns": ["payload"], "schema": schema}
    tables = [slice_entry["file"]]
    dry = restore_archive(connection, archive, tables, dry_run=True, **options)
    assert dry[0]["rows_changed"] == nulled_count(connection, schema) > 0
    gate = (PROJECT_ROOT / "db/rollbacks/0028_restore_source_record_payload.sql").read_text()
    with pytest.raises(errors.RaiseException):
        connection.execute(gate.replace("se_liga_brasil", schema))
    restore_archive(connection, archive, tables, **options)
    connection.execute(gate.replace("se_liga_brasil", schema))
    assert table_fingerprint(connection, schema, "source_record") == before_records
    assert verify_archive(connection, archive)["all_files_ok"]


def restore_whole_tables(connection, schema, archive, before_probe):
    """Identity ids, uuid, timestamptz, arrays, bytea, jsonb and a table without primary key."""
    connection.execute(f"TRUNCATE {schema}.archive_type_probe, {schema}.archive_no_key_probe")
    results = restore_archive(
        connection, archive, ["archive_type_probe", "archive_no_key_probe"], schema=schema
    )
    assert {r["file"]: r["rows_changed"] for r in results} == {
        f"{schema}.archive_type_probe.ndjson.gz": 3000,
        f"{schema}.archive_no_key_probe.ndjson.gz": 3,
    }
    with pytest.raises(ArchiveError):  # keyless table is no longer empty: no silent duplicates
        restore_archive(connection, archive, ["archive_no_key_probe"], schema=schema)
    assert table_fingerprint(connection, schema, "archive_type_probe") == before_probe
    new_id = connection.execute(
        f"INSERT INTO {schema}.archive_type_probe(owner,seen_at,tags) VALUES(%s,now(),'{{}}') "
        "RETURNING id",
        (uuid4(),),
    ).fetchone()["id"]
    assert new_id > 3000


def test_export_verify_migrate_restore_round_trip(archive_database, tmp_path):
    connection, schema = archive_database
    seed_records(connection, schema)
    seed_probe_tables(connection, schema)
    before_records = table_fingerprint(connection, schema, "source_record")
    before_probe = table_fingerprint(connection, schema, "archive_type_probe")
    archive = tmp_path / "snapshot"
    slice_entry = export_snapshot_and_verify(connection, schema, archive)
    apply_migration_0028(connection, schema)
    roll_back_payloads(connection, schema, archive, slice_entry, before_records)
    restore_whole_tables(connection, schema, archive, before_probe)


def nulled_count(connection, schema):
    return connection.execute(
        f"SELECT count(*) AS n FROM {schema}.source_record WHERE payload IS NULL"
    ).fetchone()["n"]


def test_snapshot_connection_is_read_only_and_verify_detects_damage(archive_database, tmp_path):
    connection, schema = archive_database
    seed_probe_tables(connection, schema)
    with read_only_snapshot(connection), pytest.raises(errors.ReadOnlySqlTransaction):
        connection.execute(f"DELETE FROM {schema}.archive_type_probe")
    assert connection.autocommit and not connection.read_only
    archive = tmp_path / "a"
    targets = [t for t in snapshot_targets(connection, schema) if t.table == "archive_type_probe"]
    export_archive(connection, targets, archive, "snapshot")
    assert verify_archive(connection, archive)["all_files_ok"]

    connection.execute(f"UPDATE {schema}.archive_type_probe SET note='changed' WHERE id=5")
    report = verify_archive(connection, archive)
    assert not report["all_files_ok"]
    assert report["files"][0]["rows_differing_from_database"] == 1

    path = archive / f"{schema}.archive_type_probe.ndjson.gz"
    path.write_bytes(path.read_bytes()[:-20])
    assert not verify_archive(connection, archive)["files"][0]["file_ok"]
    with pytest.raises(ArchiveError):
        restore_archive(connection, archive, None, schema=schema)


def test_removal_targets_scope_and_nonempty_directory(archive_database, tmp_path):
    connection, schema = archive_database
    seed_records(connection, schema)
    archive = tmp_path / "removal"
    existing = {
        r["relname"]
        for r in connection.execute(
            "SELECT relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname=%s AND relkind='r'",
            (schema,),
        )
    }
    targets = removal_targets(schema, existing)
    assert {t.table for t in targets} == {"source_record"} | (
        existing
        & {"ingestion_entity_version", "ingestion_artifact_entity", "person_activity_context"}
    )
    result = export_archive(connection, targets, archive, "removal-targets")
    assert len(result["files"]) == len(targets)
    with pytest.raises(ArchiveError):
        export_archive(connection, targets, archive, "removal-targets")
    manifest = json.loads((archive / "manifest.json").read_text())
    assert re.fullmatch(r"[a-f0-9]{64}", manifest["files"][0]["file_sha256"])
    with gzip.open(archive / manifest["files"][0]["file"], "rt", encoding="utf-8") as stream:
        assert json.loads(next(stream))["row"]
