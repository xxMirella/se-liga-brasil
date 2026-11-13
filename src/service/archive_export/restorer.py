"""Restore archived rows into PostgreSQL: missing rows back, or NULL columns filled in place.

Rows travel as JSON through `jsonb_populate_recordset(NULL::table, ...)`, so every column type is
rebuilt by PostgreSQL itself. `insert` adds rows whose primary key is absent (never overwrites);
`fill-null-columns` writes only into columns that are NULL today (never overwrites a value).
"""

from contextlib import nullcontext
from pathlib import Path

from psycopg import sql

from service.archive_export.contracts import ArchiveError, require_identifier
from service.archive_export.manifest import read_manifest, select_entries
from service.archive_export.verifier import inspect_file, iter_archived_rows

MODES = ("insert", "fill-null-columns")
BATCH_ROWS = 1000


def recordset_source(table: sql.Identifier) -> sql.Composed:
    return sql.SQL("jsonb_populate_recordset(NULL::") + table + sql.SQL(", %s::jsonb)")


def build_insert_statement(table: sql.Identifier, entry: dict) -> sql.Composed:
    columns = sql.SQL(", ").join(sql.Identifier(name) for name in entry["columns"])
    override = sql.SQL(" OVERRIDING SYSTEM VALUE") if entry["identity_columns"] else sql.SQL("")
    return (
        sql.SQL("INSERT INTO ")
        + table
        + sql.SQL(" (")
        + columns
        + sql.SQL(")")
        + override
        + sql.SQL(" SELECT ")
        + columns
        + sql.SQL(" FROM ")
        + recordset_source(table)
        + sql.SQL(" ON CONFLICT DO NOTHING")
    )


def build_fill_statement(table: sql.Identifier, entry: dict, columns: list[str]) -> sql.Composed:
    assignments = sql.SQL(", ").join(
        sql.Identifier(name)
        + sql.SQL(" = coalesce(t.")
        + sql.Identifier(name)
        + sql.SQL(", r.")
        + sql.Identifier(name)
        + sql.SQL(")")
        for name in columns
    )
    same_row = sql.SQL(" AND ").join(
        sql.SQL("t.") + sql.Identifier(name) + sql.SQL(" = r.") + sql.Identifier(name)
        for name in entry["primary_key"]
    )
    needs_fill = sql.SQL(" OR ").join(
        sql.SQL("(t.")
        + sql.Identifier(name)
        + sql.SQL(" IS NULL AND r.")
        + sql.Identifier(name)
        + sql.SQL(" IS NOT NULL)")
        for name in columns
    )
    return (
        sql.SQL("UPDATE ")
        + table
        + sql.SQL(" AS t SET ")
        + assignments
        + sql.SQL(" FROM ")
        + recordset_source(table)
        + sql.SQL(" AS r WHERE ")
        + same_row
        + sql.SQL(" AND (")
        + needs_fill
        + sql.SQL(")")
    )


def choose_fill_columns(entry: dict, requested: list[str] | None) -> list[str]:
    if not entry["primary_key"]:
        raise ArchiveError("FILL_NULL_COLUMNS_REQUIRES_PRIMARY_KEY")
    if not requested:
        raise ArchiveError("FILL_NULL_COLUMNS_REQUIRES_COLUMNS")
    invalid = set(requested) - set(entry["columns"]) | set(requested) & set(entry["primary_key"])
    if invalid:
        raise ArchiveError("INVALID_FILL_COLUMNS:" + ",".join(sorted(invalid)))
    return requested


def batched(rows, size: int = BATCH_ROWS):
    batch: list[str] = []
    for row in rows:
        batch.append(row.row_text)
        if len(batch) == size:
            yield "[" + ",".join(batch) + "]"
            batch = []
    if batch:
        yield "[" + ",".join(batch) + "]"


def advance_identity_sequences(connection, table: sql.Identifier, schema: str, entry: dict) -> None:
    """After inserting explicit ids, make nextval() safe: it must exceed the largest restored id."""
    for column in entry["identity_columns"]:
        connection.execute(
            sql.SQL(
                "SELECT setval(seq, m, true) FROM (SELECT pg_get_serial_sequence(%s, %s) AS seq, "
                "(SELECT max("
            )
            + sql.Identifier(column)
            + sql.SQL(") FROM ")
            + table
            + sql.SQL(") AS m) x WHERE m IS NOT NULL AND seq IS NOT NULL"),
            (f'"{schema}"."{entry["table"]}"', column),
        )


def apply_batches(connection, path: Path, statement, dry_run: bool) -> int:
    """Real runs commit every batch (idempotent, resumable); a dry run stays in one rollback."""
    changed = 0
    for batch in batched(iter_archived_rows(path)):
        if dry_run:
            changed += connection.execute(statement, (batch,)).rowcount
            continue
        with connection.transaction():
            changed += connection.execute(statement, (batch,)).rowcount
    return changed


def require_empty_when_keyless(connection, table: sql.Identifier, entry: dict) -> None:
    """Without a primary key a re-run could not tell restored rows from existing ones."""
    if entry["primary_key"]:
        return
    query = sql.SQL("SELECT EXISTS(SELECT 1 FROM ") + table + sql.SQL(") AS has_rows")
    row = connection.execute(query).fetchone()
    if row["has_rows"] if isinstance(row, dict) else row[0]:
        raise ArchiveError("KEYLESS_TABLE_RESTORE_REQUIRES_EMPTY_TABLE:" + entry["table"])


def restore_entry(connection, directory: Path, entry: dict, options: dict) -> dict:
    schema = require_identifier(options["schema"] or entry["schema"])
    table = sql.Identifier(schema, require_identifier(entry["table"]))
    if options["mode"] == "insert":
        require_empty_when_keyless(connection, table, entry)
        statement = build_insert_statement(table, entry)
    else:
        statement = build_fill_statement(
            table, entry, choose_fill_columns(entry, options["columns"])
        )
    outer = connection.transaction(force_rollback=True) if options["dry_run"] else nullcontext()
    with outer:
        changed = apply_batches(
            connection, directory / entry["file"], statement, options["dry_run"]
        )
        if options["mode"] == "insert":
            advance_identity_sequences(connection, table, schema, entry)
    return {
        "file": entry["file"],
        "rows_in_archive": entry["row_count"],
        "rows_changed": changed,
        "dry_run": options["dry_run"],
    }


def restore_archive(
    connection,
    directory: Path,
    tables: list[str] | None,
    mode: str = "insert",
    columns: list[str] | None = None,
    dry_run: bool = False,
    schema: str | None = None,
) -> list[dict]:
    if mode not in MODES:
        raise ArchiveError(f"UNKNOWN_RESTORE_MODE:{mode}")
    if not connection.autocommit:
        raise ArchiveError("RESTORE_REQUIRES_AUTOCOMMIT_CONNECTION")
    manifest = read_manifest(directory)
    entries = select_entries(manifest, tables)
    if not entries:
        raise ArchiveError("NO_ARCHIVED_FILE_MATCHES_TABLE_FILTER")
    for entry in entries:
        if not inspect_file(directory, entry)["file_ok"]:
            raise ArchiveError("ARCHIVE_FILE_FAILED_INTEGRITY_CHECK:" + entry["file"])
    options = {"mode": mode, "columns": columns, "dry_run": dry_run, "schema": schema}
    return [restore_entry(connection, directory, entry, options) for entry in entries]
