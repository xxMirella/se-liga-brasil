from datetime import date

import pytest

from service.serving import DatasetSpec, build_dataset, current_release, rebuild_serving_datasets

pytestmark = pytest.mark.integration

TODAY = date(2026, 11, 5)


def numbers(count):
    return DatasetSpec(
        name="numbers",
        columns_ddl="value int PRIMARY KEY",
        indexes=("(value DESC)",),
        insert_sql=f"INSERT INTO {{table}}(value) SELECT generate_series(1,{count})",
    )


def test_rebuild_swaps_table_and_failure_keeps_the_served_one(integration_database):
    first = build_dataset(integration_database, numbers(3), TODAY)
    again = build_dataset(integration_database, numbers(3), TODAY)
    assert first.version == again.version
    broken = DatasetSpec(
        name="numbers",
        columns_ddl="value int PRIMARY KEY",
        insert_sql="INSERT INTO {table}(value) VALUES (1),(1)",
    )
    with pytest.raises(Exception, match="duplicate key"):
        build_dataset(integration_database, broken, TODAY)
    count = integration_database.execute(
        "SELECT count(*)::int AS n FROM se_liga_brasil_serving.numbers"
    ).fetchone()["n"]
    assert count == 3
    assert current_release(integration_database, "numbers", TODAY).row_count == 3
    build_dataset(integration_database, numbers(5), TODAY)
    assert current_release(integration_database, "numbers", TODAY).row_count == 5


def served_values(connection):
    rows = connection.execute(
        "SELECT value FROM se_liga_brasil_serving.numbers ORDER BY value"
    ).fetchall()
    return [row["value"] for row in rows]


def test_failure_after_populate_still_keeps_table_release_and_no_staging(integration_database):
    first = build_dataset(integration_database, numbers(3), TODAY)
    failing_index = DatasetSpec(
        name="numbers",
        columns_ddl="value int PRIMARY KEY",
        indexes=("(no_such_column)",),
        insert_sql="INSERT INTO {table}(value) SELECT generate_series(10,20)",
    )
    with pytest.raises(Exception, match="no_such_column"):
        build_dataset(integration_database, failing_index, date(2026, 11, 6))
    assert served_values(integration_database) == [1, 2, 3]
    release = current_release(integration_database, "numbers", TODAY)
    assert (release.version, release.as_of) == (first.version, TODAY)
    leftovers = integration_database.execute(
        "SELECT count(*)::int AS n FROM pg_tables"
        " WHERE schemaname='se_liga_brasil_serving' AND tablename LIKE '%__staging'"
    ).fetchone()["n"]
    assert leftovers == 0


def test_registry_hook_reports_failure_and_serves_the_previous_release(integration_database):
    first = build_dataset(integration_database, numbers(3), TODAY)

    def broken(_connection, _as_of):
        return DatasetSpec(
            name="numbers",
            columns_ddl="value int PRIMARY KEY",
            insert_sql="INSERT INTO {table}(value) VALUES (7),(7)",
        )

    outcomes = rebuild_serving_datasets(integration_database, TODAY, {"numbers": broken})
    assert outcomes == {"numbers": "failed:UniqueViolation"}
    assert served_values(integration_database) == [1, 2, 3]
    assert current_release(integration_database, "numbers", TODAY).version == first.version
    healthy = rebuild_serving_datasets(
        integration_database, TODAY, {"numbers": lambda _c, _d: numbers(3)}
    )
    assert healthy == {"numbers": first.version}
