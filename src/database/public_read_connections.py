"""Reusable read-only connections for public requests; crawlers keep their own session mode.

Opening a PostgreSQL connection (TCP, TLS, authentication) costs far more than the indexed
reads behind a public page. Warm serverless instances and long-lived servers therefore keep a
few idle connections, discard them when old, broken or inside a transaction, and retry once
on a fresh connection if a pooled one turns out to be dead.
"""

import os
import re
from contextlib import suppress
from pathlib import Path
from threading import Lock
from time import monotonic

import psycopg
from dotenv import load_dotenv
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.pq import TransactionStatus
from psycopg.rows import dict_row

from service.ingestion.contracts import IngestionError

MAX_IDLE_CONNECTIONS = 2
MAX_IDLE_AGE_SECONDS = 60.0
TRANSACTION_POOLER_PORT = "6543"


def public_read_connection_string(connection_string: str) -> str:
    """Reads need no session state: use the pooler's transaction mode when it is a pooler."""
    parameters = conninfo_to_dict(connection_string)
    host = parameters.get("host", "")
    if host.endswith(".pooler.supabase.com") and parameters.get("port") in {None, "5432"}:
        return make_conninfo(connection_string, port=TRANSACTION_POOLER_PORT)
    return connection_string


def open_public_read_connection(env_file: Path | None = None) -> psycopg.Connection:
    if env_file:
        load_dotenv(env_file, override=False)
    connection_string = os.getenv("DATABASE_URL") or os.getenv("SUPABASE_URL", "")
    if not re.match(r"^postgres(?:ql)?://", connection_string):
        raise IngestionError("POSTGRES_CONNECTION_REQUIRED")
    return psycopg.connect(
        public_read_connection_string(connection_string),
        prepare_threshold=None,
        autocommit=True,
        row_factory=dict_row,
        connect_timeout=15,
        application_name="se-liga-brasil-public-read",
    )


class PublicReadConnectionPool:
    def __init__(
        self,
        opener,
        *,
        max_idle=MAX_IDLE_CONNECTIONS,
        max_idle_age=MAX_IDLE_AGE_SECONDS,
        clock=monotonic,
    ):
        self.opener, self.max_idle, self.max_idle_age, self.clock = (
            opener,
            max_idle,
            max_idle_age,
            clock,
        )
        self._idle = []
        self._lock = Lock()

    def read(self, operation):
        """Run operation(connection). A reused connection found dead is replaced once."""
        connection, reused = self._checkout()
        try:
            result = operation(connection)
        except BaseException as error:
            died = connection.closed or connection.broken
            self._discard(connection)
            if not (reused and died and isinstance(error, psycopg.OperationalError)):
                raise
            return self._read_on_fresh_connection(operation)
        self._checkin(connection)
        return result

    def _read_on_fresh_connection(self, operation):
        connection = self.opener()
        try:
            return operation(connection)
        finally:
            self._checkin(connection)

    def close(self):
        with self._lock:
            idle, self._idle = self._idle, []
        for _, connection in idle:
            self._discard(connection)

    def _checkout(self):
        with self._lock:
            while self._idle:
                stored_at, connection = self._idle.pop()
                if self._is_reusable(connection, stored_at):
                    return connection, True
                self._discard(connection)
        return self.opener(), False

    def _is_reusable(self, connection, stored_at):
        return (
            not connection.closed
            and not connection.broken
            and connection.info.transaction_status == TransactionStatus.IDLE
            and self.clock() - stored_at <= self.max_idle_age
        )

    def _checkin(self, connection):
        with self._lock:
            reusable = self._is_reusable(connection, self.clock())
            if reusable and len(self._idle) < self.max_idle:
                self._idle.append((self.clock(), connection))
                return
        self._discard(connection)

    @staticmethod
    def _discard(connection):
        with suppress(psycopg.Error):
            connection.close()
