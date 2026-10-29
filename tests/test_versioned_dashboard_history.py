"""Changing the selected year reuses the published history of the territory (isolated SQL)."""

from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import psycopg.errors

from database.operations import read_sql_file
from database.political_dashboard_analytical import AnnualDashboardRepository
from database.political_dashboard_history import SNAPSHOT_QUERY
from service.political_dashboard_dataset.history_cache import VersionedHistoryCache


class RecordingSnapshotConnection:
    """Records which history payloads travelled; optionally pretends the table is missing."""

    def __init__(self, connection, *, history_table_missing=False):
        self.connection = connection
        self.history_table_missing = history_table_missing
        self.transmitted = []
        self.info = connection.info

    def execute(self, query, parameters=None):
        if query != SNAPSHOT_QUERY:
            return self.connection.execute(query, parameters)
        if self.history_table_missing:
            raise psycopg.errors.UndefinedTable("political_dashboard_history")
        result = self.connection.execute(query, parameters).fetchone()
        self.transmitted.append(
            sorted(h["territory_code"] for h in result["histories"] if h["payload_base64"])
        )
        return SimpleNamespace(fetchone=lambda: result)

    def transaction(self):
        return self.connection.transaction()


def annual_partition(year, *, territory="BR", abbreviation="PT"):
    return {
        "year": year, "territory_code": territory, "institution_code": "senado",
        "office_kinds": ["senator"], "total": 81, "coverage": "observed_complete",
        "political_parties": [{"abbreviation": abbreviation, "count": 81}],
        "members": [{"name": "Only selected-year detail requires this"}],
    }


def history_repository(integration_database, *, with_history_table=True, missing=False):
    integration_database.execute(read_sql_file("political_dashboard_annual.sql"))
    if with_history_table:
        integration_database.execute(read_sql_file("political_dashboard_history.sql"))
    connection = RecordingSnapshotConnection(integration_database, history_table_missing=missing)
    repository = AnnualDashboardRepository(connection, history_cache=VersionedHistoryCache())
    publisher = AnnualDashboardRepository(integration_database)
    publisher.activate_partitions([annual_partition(2024), annual_partition(2025)])
    return repository, publisher, connection


def test_selected_year_change_does_not_retransmit_or_mutate_same_version(integration_database):
    repository, _, connection = history_repository(integration_database)
    first = repository.fetch_annual_snapshot(2024, ["BR"], 2026)
    first["history"][0]["composition"]["political_parties"][0]["count"] = 0
    second = repository.fetch_annual_snapshot(2025, ["BR"], 2026)
    assert second["partitions"][0]["payload"]["year"] == 2025
    assert second["history"][0]["composition"]["political_parties"][0]["count"] == 81
    assert "members" not in second["history"][0]["composition"]
    assert connection.transmitted == [["BR"], []]
    assert first["dataset_version"] != second["dataset_version"]


def test_dataset_version_changes_with_selected_partition_and_with_publication(
    integration_database,
):
    repository, publisher, _ = history_repository(integration_database)
    v2024 = repository.fetch_annual_snapshot(2024, ["BR"], 2026)["dataset_version"]
    v2025 = repository.fetch_annual_snapshot(2025, ["BR"], 2026)["dataset_version"]
    publisher.activate_partitions([annual_partition(2024, abbreviation="PL")])
    republished = repository.fetch_annual_snapshot(2024, ["BR"], 2026)["dataset_version"]
    assert len({v2024, v2025, republished}) == 3


def test_publication_refreshes_history_and_invalidates_cache(integration_database):
    repository, publisher, connection = history_repository(integration_database)
    repository.fetch_annual_snapshot(2024, ["BR"], 2026)
    publisher.activate_partitions([annual_partition(2024, abbreviation="PL")])
    changed = repository.fetch_annual_snapshot(2024, ["BR"], 2026)
    assert connection.transmitted[-1] == ["BR"]
    assert changed["partitions"][0]["payload"]["political_parties"][0]["abbreviation"] == "PL"
    first_row = [row for row in changed["history"] if row["year"] == 2024][0]
    assert first_row["composition"]["political_parties"][0]["abbreviation"] == "PL"


def test_republishing_identical_data_keeps_history_version(integration_database):
    repository, publisher, connection = history_repository(integration_database)
    repository.fetch_annual_snapshot(2024, ["BR"], 2026)
    publisher.activate_partitions([annual_partition(2024)])
    repository.fetch_annual_snapshot(2024, ["BR"], 2026)
    assert connection.transmitted == [["BR"], []]


def test_each_territory_has_its_own_version(integration_database):
    repository, publisher, connection = history_repository(integration_database)
    repository.fetch_annual_snapshot(2024, ["BR"], 2026)
    publisher.activate_partitions([annual_partition(2024, territory="SP", abbreviation="PL")])
    repository.fetch_annual_snapshot(2025, ["BR"], 2026)
    assert connection.transmitted[-1] == []
    state = repository.fetch_annual_snapshot(2024, ["SP"], 2026)
    assert {row["territory_code"] for row in state["history"]} == {"SP"}
    both = repository.fetch_annual_snapshot(2024, ["BR", "SP"], 2026)
    assert connection.transmitted[-1] == []
    assert [(row["year"], row["territory_code"]) for row in both["history"]] == [
        (2024, "BR"), (2024, "SP"), (2025, "BR"),
    ]


def test_concurrent_year_requests_transmit_same_history_once(integration_database):
    repository, _, connection = history_repository(integration_database)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(
            lambda year: repository.fetch_annual_snapshot(year, ["BR"], 2026),
            [2024, 2025, 2024, 2025],
        ))
    assert all(len(result["history"]) == 2 for result in results)
    assert sum(len(batch) for batch in connection.transmitted) == 1


def test_missing_history_table_falls_back_to_annual_rows_with_same_content(integration_database):
    repository, _, _ = history_repository(integration_database)
    published = repository.fetch_annual_snapshot(2024, ["BR"], 2026)["history"]
    fallback_connection = RecordingSnapshotConnection(
        integration_database, history_table_missing=True
    )
    fallback = AnnualDashboardRepository(
        fallback_connection, history_cache=VersionedHistoryCache()
    ).fetch_annual_snapshot(2024, ["BR"], 2026)
    assert fallback["history"] == published
    assert fallback.get("dataset_version") is None


def test_unpublished_territory_falls_back_without_error(integration_database):
    repository, _, _ = history_repository(integration_database)
    integration_database.execute("DELETE FROM se_liga_brasil.political_dashboard_history")
    snapshot = repository.fetch_annual_snapshot(2024, ["BR"], 2026)
    assert len(snapshot["history"]) == 2


def test_publishing_before_the_history_migration_is_a_noop_for_history(integration_database):
    history_repository(integration_database, with_history_table=False)
    stored = integration_database.execute(
        "SELECT count(*) AS n FROM se_liga_brasil.political_dashboard_annual"
    ).fetchone()["n"]
    assert stored == 2


def test_history_cache_limits_and_versions_preserve_immutable_local_reference():
    cache = VersionedHistoryCache(capacity=1, max_bytes=50)
    cache.store("BR", "v1", [{"year": 2024}])
    retained = cache.get("BR")
    cache.store("SP", "v2", [{"year": 2025}])
    assert cache.get("BR") is None
    assert retained.version == "v1" and retained.rows() == [{"year": 2024}]
    cache.store("oversized", "v3", [{"detail": "x" * 100}])
    assert cache.get("oversized") is None
    assert cache.get("SP").version == "v2"
