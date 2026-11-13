"""The SELECT that both export and verify run, so they enumerate rows identically."""

from psycopg import sql

from service.archive_export.catalog import TableDescription
from service.archive_export.contracts import ArchiveTarget, require_identifier

ROW_TEXT_EXPRESSION = "to_jsonb(t)::text"
ROW_DIGEST_EXPRESSION = "encode(sha256(convert_to(to_jsonb(t)::text, 'UTF8')), 'hex')"


def build_ordered_select(
    target: ArchiveTarget, description: TableDescription, value_expression: str
) -> sql.Composed:
    """key_text, <value_expression> of every row of the target, in a stable primary-key order."""
    table = sql.Identifier(require_identifier(target.schema), require_identifier(target.table))
    key_columns = [sql.Identifier(name) for name in description.primary_key]
    key_expression = (
        sql.SQL("jsonb_build_array(")
        + sql.SQL(", ").join(sql.SQL("t.") + column for column in key_columns)
        + sql.SQL(")::text")
        if key_columns
        else sql.SQL("'[]'")
    )
    ordering = (
        sql.SQL(", ").join(sql.SQL("t.") + column for column in key_columns)
        if key_columns
        else sql.SQL(ROW_TEXT_EXPRESSION)
    )
    where = (
        sql.SQL(" WHERE " + target.slice_predicate_sql)
        if target.slice_predicate_sql
        else sql.SQL("")
    )
    return (
        sql.SQL("SELECT ")
        + key_expression
        + sql.SQL(", " + value_expression + " FROM ")
        + table
        + sql.SQL(" AS t")
        + where
        + sql.SQL(" ORDER BY ")
        + ordering
    )
