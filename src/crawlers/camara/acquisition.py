"""Immutable downloads, pagination bounds and shared cache for official resources."""

import json
from datetime import UTC, datetime

from crawlers.camara.configuration import API_BASE
from service.acquisition.downloader import download_resource
from service.ingestion.contracts import DownloadBudget, IngestionError, Resource
from storage.files import hash_content


class CamaraAcquisition:
    def __init__(self, configuration, client) -> None:
        self.configuration = configuration
        self.client = client
        self.budget = DownloadBudget()

    def acquire(self, url, kind, suffix=".json"):
        resource = Resource(
            "camara-" + hash_content(url),
            kind,
            url,
            kind,
            datetime.now(UTC).year,
            "camara-enrichment",
            file_suffix=suffix,
        )
        return download_resource(resource, self.configuration, self.client, self.budget)

    def json_document(self, path, kind):
        url = path if path.startswith("https://") else API_BASE + path
        artifact = self.acquire(url, kind)
        return json.loads(artifact.path.read_bytes()), artifact

    def pages(self, path, kind):
        seen = set()
        for _ in range(self.configuration.max_pages):
            if path in seen:
                raise IngestionError("CAMARA_PAGINATION_CYCLE")
            seen.add(path)
            document, artifact = self.json_document(path, kind)
            if not isinstance(document.get("dados"), list):
                raise IngestionError("CAMARA_API_SCHEMA_CHANGED")
            yield document["dados"], artifact
            path = next((x["href"] for x in document.get("links", []) if x["rel"] == "next"), None)
            if path is None:
                return
        raise IngestionError("CAMARA_PAGE_LIMIT_EXCEEDED")
