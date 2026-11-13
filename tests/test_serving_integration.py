from datetime import date

import pytest

from service.serving import DatasetSpec, build_dataset, current_release

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
