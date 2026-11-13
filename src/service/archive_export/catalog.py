"""PostgreSQL catalog facts the archive needs: columns, keys, identity and dependency order."""

import hashlib
from dataclasses import dataclass

from service.archive_export.snapshot_connection import fetch_dicts

COLUMNS_SQL = """
SELECT a.attname AS name, a.attgenerated <> '' AS is_generated, a.attidentity <> '' AS is_identity,
  format_type(a.atttypid, a.atttypmod) AS type_name
FROM pg_attribute a WHERE a.attrelid = %s::regclass AND a.attnum > 0 AND NOT a.attisdropped
ORDER BY a.attnum"""
PRIMARY_KEY_SQL = """
SELECT a.attname AS name FROM pg_index i
CROSS JOIN LATERAL unnest(i.indkey) WITH ORDINALITY AS k(attnum, position)
JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = k.attnum
WHERE i.indrelid = %s::regclass AND i.indisprimary ORDER BY k.position"""
TABLES_SQL = """
SELECT c.relname AS name, pg_total_relation_size(c.oid) AS total_bytes, c.reltuples::bigint AS rows
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = %s AND c.relkind IN ('r', 'p') AND NOT c.relispartition ORDER BY c.relname"""
FOREIGN_KEYS_SQL = """
SELECT child.relname AS child, parent.relname AS parent FROM pg_constraint k
JOIN pg_class child ON child.oid = k.conrelid JOIN pg_class parent ON parent.oid = k.confrelid
JOIN pg_namespace n ON n.oid = child.relnamespace AND n.nspname = %s
JOIN pg_namespace pn ON pn.oid = parent.relnamespace AND pn.nspname = %s
WHERE k.contype = 'f' AND child.oid <> parent.oid"""


@dataclass(frozen=True)
class TableDescription:
    columns: tuple[str, ...]
    primary_key: tuple[str, ...]
    identity_columns: tuple[str, ...]
    column_types: dict


def qualified(schema: str, table: str) -> str:
    return f'"{schema}"."{table}"'


def describe_table(connection, schema: str, table: str) -> TableDescription:
    rows = fetch_dicts(connection, COLUMNS_SQL, (qualified(schema, table),))
    stored = [row for row in rows if not row["is_generated"]]
    primary_key = fetch_dicts(connection, PRIMARY_KEY_SQL, (qualified(schema, table),))
    return TableDescription(
        columns=tuple(row["name"] for row in stored),
        primary_key=tuple(row["name"] for row in primary_key),
        identity_columns=tuple(row["name"] for row in stored if row["is_identity"]),
        column_types={row["name"]: row["type_name"] for row in stored},
    )


def list_tables(connection, schema: str) -> list[dict]:
    return fetch_dicts(connection, TABLES_SQL, (schema,))


def order_by_foreign_keys(connection, schema: str, tables: list[str]) -> list[str]:
    """Parents before children, so a whole-schema restore satisfies foreign keys."""
    edges = fetch_dicts(connection, FOREIGN_KEYS_SQL, (schema, schema))
    waiting = {name: set() for name in tables}
    for edge in edges:
        if edge["child"] in waiting and edge["parent"] in waiting:
            waiting[edge["child"]].add(edge["parent"])
    ordered: list[str] = []
    while waiting:
        ready = sorted(name for name, parents in waiting.items() if not parents)
        ready = ready or sorted(waiting)  # dependency cycle: keep deterministic order
        for name in ready:
            ordered.append(name)
            del waiting[name]
        for parents in waiting.values():
            parents.difference_update(ready)
    return ordered


def schema_fingerprint(connection, schema: str) -> str:
    """SHA-256 of every table, column and type of the schema: the archive's schema version."""
    lines = []
    for table in list_tables(connection, schema):
        description = describe_table(connection, schema, table["name"])
        for column in description.columns:
            lines.append(f"{table['name']}.{column}:{description.column_types[column]}")
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()
