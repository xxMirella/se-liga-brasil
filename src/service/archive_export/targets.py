"""Which tables and slices each archive scope contains."""

from service.archive_export.catalog import list_tables, order_by_foreign_keys
from service.archive_export.contracts import ArchiveError, ArchiveTarget, require_identifier
from service.archive_export.source_record_types import source_record_payload_predicate_sql

MAIN_SCHEMA = "se_liga_brasil"
SERVING_SCHEMA = "se_liga_brasil_serving"
SERVING_RELEASE_TABLE = "dataset_release"
UNREAD_PAYLOAD_SLICE = "payload_without_readers"
REMOVAL_TABLES = (
    "ingestion_entity_version",
    "ingestion_artifact_entity",
    "person_activity_context",
)
SCOPES = ("snapshot", "removal-targets")


def unread_payload_target(schema: str) -> ArchiveTarget:
    schema = require_identifier(schema)
    predicate = (
        f'EXISTS (SELECT 1 FROM "{schema}".source s WHERE s.id = t.source_id AND '
        + source_record_payload_predicate_sql("t", "s")
        + ")"
    )
    return ArchiveTarget(
        schema=schema,
        table="source_record",
        slice_name=UNREAD_PAYLOAD_SLICE,
        slice_predicate_sql=predicate,
        verify_source_record_payload_hash=True,
        description="source_record rows whose payload migration 0028 sets to NULL",
    )


def removal_targets(
    schema: str = MAIN_SCHEMA, existing_tables: set[str] | None = None
) -> list[ArchiveTarget]:
    """The R4 slice plus the tables other migrations remove (skipped when already dropped)."""
    names = [name for name in REMOVAL_TABLES if existing_tables is None or name in existing_tables]
    whole = [ArchiveTarget(schema, name) for name in names]
    return [unread_payload_target(schema), *whole]


def snapshot_targets(connection, schema: str = MAIN_SCHEMA, serving_schema: str | None = None):
    """Every table of the main schema (parents first), the release metadata and the R4 slice."""
    names = [row["name"] for row in list_tables(connection, schema)]
    targets = [
        ArchiveTarget(schema, name) for name in order_by_foreign_keys(connection, schema, names)
    ]
    serving = serving_schema or SERVING_SCHEMA
    serving_tables = {row["name"] for row in list_tables(connection, serving)}
    if SERVING_RELEASE_TABLE in serving_tables:
        targets.append(
            ArchiveTarget(serving, SERVING_RELEASE_TABLE, description="release versions")
        )
    return [*targets, unread_payload_target(schema)]


def select_targets(connection, scope: str, tables: list[str] | None, schema: str = MAIN_SCHEMA):
    if scope not in SCOPES:
        raise ArchiveError(f"UNKNOWN_SCOPE:{scope}")
    existing = {row["name"] for row in list_tables(connection, schema)}
    targets = (
        removal_targets(schema, existing)
        if scope == "removal-targets"
        else snapshot_targets(connection, schema, f"{schema}_serving")
    )
    if not tables:
        return targets
    wanted = set(tables)
    chosen = [target for target in targets if wanted & {target.table, target.file_name}]
    if not chosen:
        raise ArchiveError("NO_TARGET_MATCHES_TABLE_FILTER")
    return chosen
