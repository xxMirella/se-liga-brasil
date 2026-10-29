"""Public read connections are reused safely; crawlers keep session mode."""

from types import SimpleNamespace

import psycopg
import pytest
from psycopg.conninfo import conninfo_to_dict
from psycopg.pq import TransactionStatus

from application.public_cache import prepare_public_response
from database.operations import session_connection_string
from database.public_read_connections import (
    PublicReadConnectionPool,
    public_read_connection_string,
)

POOLER = "postgresql://u:p@aws-0-sa.pooler.supabase.com:{port}/postgres"


class FakeConnection:
    def __init__(self):
        self.closed = self.broken = False
        self.info = SimpleNamespace(transaction_status=TransactionStatus.IDLE)

    def close(self):
        self.closed = True


def make_pool(**options):
    opened = []

    def opener():
        opened.append(FakeConnection())
        return opened[-1]

    return PublicReadConnectionPool(opener, **options), opened


def test_pool_reuses_one_connection_across_requests():
    pool, opened = make_pool()
    for _ in range(3):
        assert pool.read(lambda connection: connection) is opened[0]
    assert len(opened) == 1


def test_pool_discards_old_in_transaction_and_failed_connections():
    now = [0.0]
    pool, opened = make_pool(max_idle_age=10, clock=lambda: now[0])
    pool.read(lambda connection: None)
    now[0] = 11
    pool.read(lambda connection: None)
    assert len(opened) == 2 and opened[0].closed
    pool.read(lambda connection: setattr(
        connection.info, "transaction_status", TransactionStatus.INTRANS))
    pool.read(lambda connection: None)
    assert len(opened) == 3
    with pytest.raises(ValueError):
        pool.read(lambda connection: (_ for _ in ()).throw(ValueError("boom")))
    assert opened[-1].closed


def test_pool_replaces_a_reused_connection_that_died_once():
    pool, opened = make_pool()
    pool.read(lambda connection: None)
    attempts = []

    def operation(connection):
        attempts.append(connection)
        if connection is opened[0]:
            connection.broken = True
            raise psycopg.OperationalError("server closed the connection")
        return "ok"

    assert pool.read(operation) == "ok"
    assert len(opened) == 2 and attempts == [opened[0], opened[1]]


def test_fresh_connection_failure_is_not_retried():
    pool, opened = make_pool()
    with pytest.raises(psycopg.OperationalError):
        pool.read(lambda connection: (_ for _ in ()).throw(psycopg.OperationalError("down")))
    assert len(opened) == 1


def port_of(connection_string):
    return conninfo_to_dict(connection_string)["port"]


def test_public_reads_use_transaction_pooler_but_crawlers_keep_session_mode():
    assert port_of(public_read_connection_string(POOLER.format(port=5432))) == "6543"
    assert port_of(public_read_connection_string(POOLER.format(port=6543))) == "6543"
    assert port_of(session_connection_string(POOLER.format(port=6543))) == "5432"
    direct = "postgresql://u:p@db.example.com:5432/postgres"
    assert public_read_connection_string(direct) == direct


def test_etag_includes_dataset_version_and_stays_stable_without_it():
    request = {"Accept-Encoding": "", "If-None-Match": ""}
    body = b"<html>same</html>"
    _, _, first = prepare_public_response("/panorama", 200, body, request, "v1")
    _, _, second = prepare_public_response("/panorama", 200, body, request, "v2")
    _, _, none = prepare_public_response("/panorama", 200, body, request)
    assert first["ETag"] != second["ETag"] != none["ETag"]
    status, _, _ = prepare_public_response(
        "/panorama", 200, body, {**request, "If-None-Match": first["ETag"]}, "v1"
    )
    assert status == 304
