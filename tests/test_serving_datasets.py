from datetime import UTC, date, datetime

import pytest
from serving_fakes import FakeServingConnection

from service.serving import (
    DatasetSpec,
    build_dataset,
    current_release,
    rebuild_serving_datasets,
)

TODAY = date(2026, 11, 5)
LIVE = "se_liga_brasil_serving.person_directory"


def spec(rows=None, **overrides):
    values = {
        "name": "person_directory",
        "columns_ddl": "person_id int PRIMARY KEY, name text",
        "columns": ("person_id", "name"),
        "rows": rows,
        "indexes": ("(name)",),
    }
    return DatasetSpec(**(values | overrides))


def test_build_swaps_staging_into_live_and_records_release():
    connection = FakeServingConnection()
    release = build_dataset(connection, spec([(1, "Ana"), (2, "Bia")]), TODAY)
    assert connection.tables[LIVE]["rows"] == [(1, "Ana"), (2, "Bia")]
    assert not any(name.endswith("__staging") for name in connection.tables)
    assert (release.name, release.row_count, release.as_of) == ("person_directory", 2, TODAY)
    assert any("CREATE INDEX ON" in sql for sql in connection.statements)
    assert any("ENABLE ROW LEVEL SECURITY" in sql for sql in connection.statements)


def test_second_build_replaces_the_first_atomically():
    connection = FakeServingConnection()
    build_dataset(connection, spec([(1, "Ana")]), TODAY)
    build_dataset(connection, spec([(3, "Caio")]), date(2026, 11, 6))
    assert connection.tables[LIVE]["rows"] == [(3, "Caio")]
    assert connection.releases["person_directory"]["as_of"] == date(2026, 11, 6)


@pytest.mark.parametrize("failing_step", ["INSERT INTO", "CREATE INDEX", "RENAME TO", "clock_"])
def test_failure_midway_keeps_previous_table_and_release(failing_step):
    connection = FakeServingConnection()
    first = build_dataset(connection, spec([(1, "Ana")]), TODAY)
    connection.fail_on = failing_step
    with pytest.raises(RuntimeError):
        build_dataset(connection, spec([(9, "Zed")]), date(2026, 11, 6))
    assert connection.tables[LIVE]["rows"] == [(1, "Ana")]
    assert connection.releases["person_directory"]["version"] == first.version
    assert set(connection.tables) == {LIVE}


def test_failure_during_row_iteration_preserves_served_data():
    connection = FakeServingConnection()
    build_dataset(connection, spec([(1, "Ana")]), TODAY)

    def broken_rows():
        yield (2, "Bia")
        raise ConnectionError("source dropped")

    with pytest.raises(ConnectionError):
        build_dataset(connection, spec(broken_rows()), TODAY)
    assert connection.tables[LIVE]["rows"] == [(1, "Ana")]


def test_rebuild_is_idempotent_and_version_is_content_stable():
    connection = FakeServingConnection()
    first = build_dataset(connection, spec([(2, "Bia"), (1, "Ana")]), TODAY)
    second = build_dataset(connection, spec([(1, "Ana"), (2, "Bia")]), TODAY)
    assert first.version == second.version
    assert connection.tables[LIVE]["rows"] == [(1, "Ana"), (2, "Bia")]
    assert len(connection.releases) == 1


def test_insert_select_source_formats_the_staging_table():
    connection = FakeServingConnection()
    sql = "INSERT INTO {table}(person_id) SELECT 1"
    release = build_dataset(connection, spec(None, columns=(), insert_sql=sql), TODAY)
    assert release.row_count == 1


@pytest.mark.parametrize(
    "overrides",
    [
        {"name": "Bad-Name"},
        {"name": "x__staging"},
        {"rows": None},
        {"columns": ()},
        {"insert_sql": "INSERT INTO {table} SELECT 1"},
    ],
)
def test_invalid_specs_are_rejected_before_any_statement(overrides):
    connection = FakeServingConnection()
    with pytest.raises(ValueError, match="SERVING_DATASET"):
        build_dataset(connection, spec(**({"rows": [(1, "Ana")]} | overrides)), TODAY)
    assert connection.statements == []


def test_current_release_returns_fresh_release_and_none_when_expired_or_missing():
    connection = FakeServingConnection()
    assert current_release(connection, "person_directory", TODAY) is None
    build_dataset(connection, spec([(1, "Ana")]), TODAY)
    assert current_release(connection, "person_directory", TODAY).row_count == 1
    assert current_release(connection, "person_directory", date(2026, 11, 6)) is not None
    assert current_release(connection, "person_directory", date(2026, 11, 7)) is None
    assert current_release(connection, "person_directory", date(2026, 11, 7), 2) is not None
    assert current_release(connection, "other", TODAY) is None


def test_current_release_is_none_before_the_migration_is_applied():
    connection = FakeServingConnection()
    connection.release_table_installed = False
    assert current_release(connection, "person_directory", TODAY) is None


def test_release_built_at_is_timezone_aware():
    connection = FakeServingConnection()
    release = build_dataset(connection, spec([(1, "Ana")]), TODAY)
    assert release.built_at <= datetime.now(UTC)


def test_empty_registry_hook_issues_no_statement():
    connection = FakeServingConnection()
    assert rebuild_serving_datasets(connection, TODAY, registry={}) == {}
    assert connection.statements == []


def test_hook_isolates_failures_between_datasets():
    connection = FakeServingConnection()

    def broken(_connection, _as_of):
        raise RuntimeError("factory failed")

    registry = {
        "bad": broken,
        "person_directory": lambda _connection, _as_of: spec([(1, "Ana")]),
    }
    outcomes = rebuild_serving_datasets(connection, TODAY, registry)
    assert outcomes["bad"] == "failed:RuntimeError"
    assert outcomes["person_directory"] == connection.releases["person_directory"]["version"]
