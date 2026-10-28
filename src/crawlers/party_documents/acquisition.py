"""Archive bounded official party documents with shared pacing, validators and hashes."""

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from service.acquisition.downloader import download_resource
from service.acquisition.http_client import OfficialHttpClient
from service.ingestion.contracts import DownloadBudget, Resource
from storage.files import hash_content


@dataclass(frozen=True)
class PartyDocumentConfiguration:
    storage_directory: Path
    max_download_bytes: int = 15 * 1024**2
    max_run_download_bytes: int = 150 * 1024**2
    request_timeout_seconds: int = 35
    max_attempts: int = 2
    force_recheck_after_hours: int = 168
    request_min_interval_seconds: float = 1.5


class PartyDocumentAcquisition:
    def __init__(self, storage, client, approved_hosts):
        self.configuration = PartyDocumentConfiguration(storage.resolve())
        self.client = OfficialHttpClient(self.configuration, client, frozenset(approved_hosts))
        self.budget = DownloadBudget()

    def acquire(self, url, suffix=".html"):
        if urlsplit(url).scheme != "https":
            raise ValueError("PARTY_DOCUMENT_REQUIRES_HTTPS")
        resource = Resource("party-document-" + hash_content(url), "party_document", url,
                            "party_document", 0, "party-documents", "BR", suffix)
        artifact = download_resource(resource, self.configuration, self.client, self.budget)
        return {"url": url, "sha256": artifact.sha256, "fetched_at": artifact.fetched_at,
                "path": str(artifact.path), "bytes": artifact.bytes_downloaded}
