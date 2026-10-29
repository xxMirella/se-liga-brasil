"""Panorama reads: one cached, connection-pooled request path for the public dashboard."""

from service.political_dashboard.contracts import DashboardQuery
from service.political_dashboard_dataset.history_cache import VersionedHistoryCache
from service.public_profile.search_cache import PublicSearchCache


class PoliticalDashboardReader:
    def __init__(self, read_connections, today):
        self.read_connections, self.today = read_connections, today
        self.dashboard_cache = PublicSearchCache(
            ttl_seconds=300, capacity=64, max_bytes=4 * 1024 * 1024
        )
        self.dashboard_history_cache = VersionedHistoryCache()
        # Positive-only memo: the annual table never disappears; absence is re-checked.
        self._dashboard_table_confirmed = False

    def fetch(self, parameters):
        query = DashboardQuery.from_parameters(parameters, self.today())
        return self.dashboard_cache.get_or_load(query, lambda: self._load(query))

    def _load(self, query):
        from service.political_dashboard_dataset.query import annual_dashboard_payload

        data = self.read_connections.read(lambda connection: self._read(connection, query))
        if data is None:
            return annual_dashboard_payload([], [], query, self.today().year)
        snapshot, catalog = data
        payload = annual_dashboard_payload(
            snapshot["partitions"], snapshot["history"], query, self.today().year
        )
        payload["dataset_version"] = snapshot.get("dataset_version")
        payload["dataset_generated_at"] = snapshot.get("dataset_generated_at")
        if catalog:
            payload["municipalities"] = catalog["municipalities"]
            payload["territorial_catalog_scope"] = catalog["temporal_scope"]
            payload["territorial_catalog_observed_at"] = catalog["observed_at"]
        return payload

    def _read(self, connection, query):
        """Database reads of one panorama request; None while the annual table is missing."""
        from database.political_dashboard_analytical import AnnualDashboardRepository
        from service.political_dashboard_dataset.query import (
            selected_territories,
            validate_municipality_catalog,
        )

        repository = AnnualDashboardRepository(
            connection, history_cache=self.dashboard_history_cache
        )
        if not self._dashboard_table_confirmed:
            self._dashboard_table_confirmed = repository.is_available()
        if not self._dashboard_table_confirmed:
            return None
        catalog = (
            repository.fetch_territorial_catalog(query.uf)
            if query.level in {"state", "municipal"}
            else None
        )
        validate_municipality_catalog(query, catalog)
        snapshot = repository.fetch_annual_snapshot(
            query.as_of.year, selected_territories(query), self.today().year
        )
        return snapshot, catalog
