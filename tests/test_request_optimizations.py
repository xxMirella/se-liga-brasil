"""Request-path optimizations: reads happen once per file version, snapshots are shared."""

import os
from contextlib import contextmanager, nullcontext
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from psycopg.pq import TransactionStatus

from application.public_cache import public_cache_policy
from application.public_portal import PublicPortalApplication, dispatch_portal_request
from database.public_profile import PublicProfileRepository
from service.public_profile_web.static_text import clear_static_text_cache, read_static_text

TODAY = date(2026, 10, 28)


def idle_connection_stub():
    return SimpleNamespace(
        closed=False, broken=False, close=lambda: None,
        info=SimpleNamespace(transaction_status=TransactionStatus.IDLE),
    )


def test_static_text_is_read_once_and_reloaded_when_file_changes(tmp_path, monkeypatch):
    clear_static_text_cache()
    target = tmp_path / "asset.css"
    target.write_text("a{}", encoding="utf-8")
    reads = []
    original = Path.read_text
    monkeypatch.setattr(
        Path, "read_text", lambda self, *a, **k: reads.append(self) or original(self, *a, **k)
    )
    assert [read_static_text(target) for _ in range(5)] == ["a{}"] * 5
    assert len(reads) == 1
    target.write_text("b{}{}", encoding="utf-8")
    os.utime(target, ns=(1, 1))
    assert read_static_text(target) == "b{}{}"
    assert len(reads) == 2


def test_stylesheets_and_pages_do_not_reread_files_per_request(monkeypatch):
    clear_static_text_cache()
    reads = []
    original = Path.read_text
    monkeypatch.setattr(
        Path, "read_text", lambda self, *a, **k: reads.append(self.name) or original(self, *a, **k)
    )
    app = SimpleNamespace(today=lambda: TODAY)
    targets = [
        "/assets/public-profile.css", "/assets/panorama.css", "/assets/civic-education.css",
        "/assets/people-viewport.js", "/favicon.ico", "/sobre", "/como-funciona",
    ]
    for target in targets:
        assert dispatch_portal_request(app, target).status == 200
    first_round = len(reads)
    for target in targets * 3:
        assert dispatch_portal_request(app, target).status == 200
    assert len(reads) == first_round


class OpenTransactionConnection:
    """Records statements and reports a transaction state like psycopg connections."""

    def __init__(self):
        self.statements = []
        self.events = []
        self.info = SimpleNamespace(transaction_status=TransactionStatus.IDLE)

    @contextmanager
    def transaction(self):
        self.events.append("begin")
        self.info.transaction_status = TransactionStatus.INTRANS
        try:
            yield
        finally:
            self.info.transaction_status = TransactionStatus.IDLE
            self.events.append("commit")

    def execute(self, statement, parameters=None):
        self.statements.append(statement)


def test_nested_read_snapshots_share_one_transaction_and_one_settings_round_trip():
    connection = OpenTransactionConnection()
    first, second = PublicProfileRepository(connection), PublicProfileRepository(connection)
    with first.read_snapshot(), second.read_snapshot(), first.read_snapshot():
        pass
    assert connection.events == ["begin", "commit"]
    assert len(connection.statements) == 1
    assert "REPEATABLE READ READ ONLY" in connection.statements[0]
    assert "statement_timeout" in connection.statements[0]


def test_sequential_snapshots_still_open_independent_transactions():
    connection = OpenTransactionConnection()
    repository = PublicProfileRepository(connection)
    for _ in range(2):
        with repository.read_snapshot():
            pass
    assert connection.events == ["begin", "commit", "begin", "commit"]


def test_dashboard_table_check_is_memoized_only_when_present(monkeypatch):
    checks = []
    availability = [False, True]
    monkeypatch.setattr(
        "database.public_read_connections.open_public_read_connection",
        lambda _env: idle_connection_stub(),
    )
    monkeypatch.setattr(
        "database.political_dashboard_analytical.AnnualDashboardRepository.is_available",
        lambda _self: checks.append(1) or availability[min(len(checks), 2) - 1],
    )
    monkeypatch.setattr(
        "database.political_dashboard_analytical.AnnualDashboardRepository.fetch_annual_snapshot",
        lambda _self, *args: {"partitions": [], "history": []},
    )
    app = PublicPortalApplication(None, None, today=lambda: TODAY)
    for year in ("2026", "2025", "2024", "2023"):
        app.fetch_political_dashboard({"year": year})
    # first call absent (re-checked), second present (remembered afterwards)
    assert len(checks) == 2


def test_cache_policy_covers_static_pages_and_viewport_script_only_when_ok():
    assert "s-maxage=3600" in public_cache_policy("/fontes-dos-dados", 200)
    assert public_cache_policy("/fontes-dos-dados", 503) == "no-store"
    assert public_cache_policy("/assets/people-viewport.js", 200).endswith("must-revalidate")
    assert public_cache_policy("/pessoas/00000000-0000-0000-0000-000000000000", 200) == "no-store"
    assert public_cache_policy("/api/people", 200) == "no-store"


class CountingConnection:
    """Counts statements and transaction openings made through the repository adapters."""

    def __init__(self, connection):
        self.connection = connection
        self.info = connection.connection.info
        self.statements = 0
        self.transactions = 0

    def execute(self, *arguments):
        self.statements += 1
        return self.connection.execute(*arguments)

    def transaction(self):
        self.transactions += 1
        return self.connection.transaction()

    def cursor(self, *arguments, **keywords):
        self.statements += 1
        return self.connection.connection.cursor(*arguments, **keywords)


def test_person_profile_uses_one_connection_and_no_extra_transactions(
    integration_database, monkeypatch
):
    from test_public_profile_integration import create_public_read_fixture

    from database import operations

    person_id, *_ = create_public_read_fixture(integration_database)
    counting, opened = CountingConnection(integration_database), []
    monkeypatch.setattr(
        operations, "connect_database", lambda *_: opened.append(1) or nullcontext(counting)
    )
    profile = PublicPortalApplication(None, None, today=lambda: date(2026, 10, 14)).fetch_person(
        person_id
    )
    assert profile["person_id"] == person_id
    assert opened == [1]
    # The fixture already holds an open transaction, which the snapshots must join.
    assert counting.transactions == 0
    assert counting.statements <= 12
