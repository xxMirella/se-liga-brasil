"""Reuse shared immutable storage, byte budget, retries, pacing and cache."""

from datetime import UTC, datetime

from service.acquisition.downloader import download_resource
from service.ingestion.contracts import DownloadBudget, Resource
from storage.files import hash_content


class AlerjAcquisition:
    def __init__(self, configuration, client):
        self.configuration = configuration
        self.client = client
        self.budget = DownloadBudget()

    def acquire(self, url, kind, suffix=".html"):
        resource = Resource(
            "alerj-" + hash_content(url),
            kind,
            url,
            kind,
            datetime.now(UTC).year,
            "alerj-enrichment",
            "RJ",
            suffix,
        )
        return download_resource(resource, self.configuration, self.client, self.budget)
