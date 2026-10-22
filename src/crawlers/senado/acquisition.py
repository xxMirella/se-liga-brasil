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
        self.payroll_snapshot = None
        self.payroll_error = None

    def json_document(self, path, kind, *, resource_year=None):
        resource = json_resource(path, kind, resource_year)
        artifact = download_resource(resource, self.configuration, self.client, self.budget)
        return json.loads(artifact.path.read_bytes()), artifact


def json_resource(path, kind, resource_year=None):
    url = path if path.startswith("https://") else API_BASE + path
    return Resource(
        "senado-" + hash_content(url), kind, url, kind,
        resource_year if resource_year is not None else datetime.now(UTC).year,
        "senado-enrichment", file_suffix=".json",
    )
