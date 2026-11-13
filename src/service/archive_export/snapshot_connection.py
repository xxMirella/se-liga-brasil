"""Read-only, single-snapshot database access for exporting and verifying."""

from contextlib import contextmanager

from psycopg import IsolationLevel
from psycopg.rows import dict_row, tuple_row

from service.archive_export.contracts import ArchiveError


@contextmanager
def read_only_snapshot(connection):
    """One consistent view (REPEATABLE READ) in which PostgreSQL rejects every write.

    The connection's previous autocommit/read-only/isolation settings are restored on exit.
    """
    if connection.info.transaction_status != 0:
        connection.rollback()
    previous = (connection.autocommit, connection.read_only, connection.isolation_level)
    connection.autocommit = False
    connection.isolation_level = IsolationLevel.REPEATABLE_READ
    connection.read_only = True
    try:
        connection.execute("SET LOCAL TIME ZONE 'UTC'")
        connection.execute("SET LOCAL statement_timeout = 0")
        require_utf8_server(connection)
        yield connection
    finally:
        connection.rollback()
        connection.isolation_level = previous[2]
        connection.read_only = previous[1]
        connection.autocommit = previous[0]


def require_utf8_server(connection) -> None:
    encoding = connection.execute("SHOW server_encoding").fetchone()
    if list(encoding.values() if isinstance(encoding, dict) else encoding)[0] != "UTF8":
        raise ArchiveError("SERVER_ENCODING_MUST_BE_UTF8")


def fetch_dicts(connection, query, parameters=None) -> list[dict]:
    with connection.cursor(row_factory=dict_row) as cursor:
        return cursor.execute(query, parameters).fetchall()


def stream_rows(connection, query, cursor_name: str, batch_size: int = 2000):
    """Server-side cursor: rows are pulled in batches, never loaded all at once."""
    with connection.cursor(name=cursor_name, row_factory=tuple_row) as cursor:
        cursor.itersize = batch_size
        cursor.execute(query)
        yield from cursor
