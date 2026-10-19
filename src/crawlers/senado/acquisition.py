"""Immutable Senate JSON acquisition through shared cache and HTTP protections."""

import json
from datetime import UTC, datetime

from crawlers.senado.configuration import API_BASE
from service.acquisition.downloader import download_resource
from service.ingestion.contracts import DownloadBudget, Resource
from storage.files import hash_content


class SenateAcquisition:
    def __init__(self, configuration, client):
        self.configuration = configuration
        self.client = client
        self.budget = DownloadBudget()

    def json_document(self, path, kind):
        url = API_BASE + path
        resource = Resource(
            "senado-" + hash_content(url),
            kind,
            url,
            kind,
            datetime.now(UTC).year,
            "senado-enrichment",
            file_suffix=".json",
        )
        artifact = download_resource(resource, self.configuration, self.client, self.budget)
        return json.loads(artifact.path.read_bytes()), artifact
