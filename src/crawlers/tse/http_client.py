"""TSE trust policy and CKAN catalog adapter over the shared HTTP client."""

import json

from crawlers.tse.configuration import OFFICIAL_HOSTS
from service.acquisition.http_client import OfficialHttpClient as SharedOfficialHttpClient
from service.acquisition.http_client import validate_official_url as validate_url
from service.ingestion.contracts import IngestionError


def validate_official_url(url: str) -> None:
    validate_url(url, OFFICIAL_HOSTS)


class OfficialHttpClient(SharedOfficialHttpClient):
    def __init__(self, configuration, client) -> None:
        super().__init__(configuration, client, OFFICIAL_HOSTS)

    def fetch_catalog(self, url: str) -> dict:
        payload = json.loads(self.fetch_bytes(url))
        if not payload.get("success"):
            raise IngestionError("CATALOG_API_FAILED")
        return payload["result"]
