"""Source-independent bounded acquisition; official source rules remain in each crawler."""

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx

from service.acquisition.downloader import download_resource
from service.ingestion.contracts import DownloadBudget, IngestionError, Resource
from storage.files import hash_content


@dataclass(frozen=True)
class RosterConfiguration:
    storage_directory: Path
    max_download_bytes: int = 10 * 1024**2
    max_run_download_bytes: int = 100 * 1024**2
    request_timeout_seconds: int = 30
    max_attempts: int = 2
    force_recheck_after_hours: int = 24


class RosterAcquisition:
    def __init__(self, configuration, client):
        self.configuration, self.client = configuration, client
        self.budget = DownloadBudget()

    def acquire(self, url, kind="assembly_roster", suffix=".html"):
        resource = Resource(
            "assembly-" + hash_content(url),
            kind,
            url,
            kind,
            datetime.now(UTC).year,
            "state-assembly-roster",
            file_suffix=suffix,
        )
        try:
            return download_resource(resource, self.configuration, self.client, self.budget)
        except httpx.TransportError as error:
            raise IngestionError(
                "OFFICIAL_ROSTER_NETWORK_ERROR",
                {
                    "retryable": True,
                    "error_type": type(error).__name__,
                },
            ) from error
