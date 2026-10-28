"""Immutable, paced acquisitions for Senate exercises and dated affiliations."""

import json
from dataclasses import dataclass
from pathlib import Path

from crawlers.senado.configuration import API_BASE, OFFICIAL_HOSTS
from service.acquisition.downloader import download_resource
from service.acquisition.http_client import OfficialHttpClient
from service.ingestion.contracts import DownloadBudget, Resource
from storage.files import hash_content


@dataclass(frozen=True)
class SenateHistoryConfiguration:
    storage_directory: Path
    max_download_bytes: int = 20 * 1024**2
    max_run_download_bytes: int = 100 * 1024**2
    request_timeout_seconds: int = 60
    max_attempts: int = 3
    force_recheck_after_hours: int = 168
    request_min_interval_seconds: float = 1.5


class SenateHistoryAcquisition:
    def __init__(self, configuration, client):
        self.configuration = configuration
        self.client = OfficialHttpClient(configuration, client, OFFICIAL_HOSTS)
        self.budget = DownloadBudget()

    def acquire(self, endpoint):
        url = API_BASE + endpoint
        resource = Resource(
            "senate-history-" + hash_content(url), "historical_exercises", url,
            "historical_exercises", 0, "senate-history", "BR", ".json",
        )
        artifact = download_resource(resource, self.configuration, self.client, self.budget)
        return json.loads(artifact.path.read_bytes()), {
            "url": url, "sha256": artifact.sha256, "fetched_at": artifact.fetched_at,
        }
