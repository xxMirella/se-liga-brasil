"""Bounded filtered pages using shared retries, immutable cache and host pacing."""

import json
from datetime import UTC, datetime
from decimal import Decimal
from urllib.parse import urlencode

from crawlers.transferegov.configuration import API_BASE, ENDPOINT_FILTERS
from service.acquisition.downloader import download_resource
from service.ingestion.contracts import DownloadBudget, IngestionError, Resource
from storage.files import hash_content


def partition_query(module, endpoint, filters):
    allowed = ENDPOINT_FILTERS.get((module, endpoint))
    if allowed is None or not filters or not set(filters) <= allowed:
        raise IngestionError("TRANSFEREGOV_INVALID_PARTITION")
    if any(value is None or str(value).strip() == "" for value in filters.values()):
        raise IngestionError("TRANSFEREGOV_EMPTY_FILTER")
    return tuple(sorted((key, str(value)) for key, value in filters.items()))


def validate_page(document, page_number, page_size):
    if not isinstance(document, dict) or not isinstance(document.get("data"), list):
        raise IngestionError("TRANSFEREGOV_SCHEMA_CHANGED")
    totals = [
        document.get(key) for key in ("total_pages", "total_items", "page_number", "page_size")
    ]
    if any(type(value) is not int or value < 0 for value in totals):
        raise IngestionError("TRANSFEREGOV_INVALID_PAGINATION")
    if document["page_number"] != page_number or document["page_size"] != page_size:
        raise IngestionError("TRANSFEREGOV_PAGINATION_DRIFT")
    if len(document["data"]) > page_size or any(
        not isinstance(row, dict) for row in document["data"]
    ):
        raise IngestionError("TRANSFEREGOV_SCHEMA_CHANGED")
    if not document["data"] and document["total_items"] != 0:
        raise IngestionError("TRANSFEREGOV_INCOMPLETE_PAGE")


class TransferegovAcquisition:
    def __init__(self, configuration, client):
        if not 1 <= configuration.page_size <= 200 or configuration.max_pages < 1:
            raise IngestionError("TRANSFEREGOV_INVALID_LIMITS")
        self.configuration = configuration
        self.client = client
        self.budget = DownloadBudget()

    def acquire(self, module, endpoint, query, page_number):
        parameters = dict(query) | {
            "pagina": page_number,
            "tamanho_da_pagina": self.configuration.page_size,
        }
        url = API_BASE + module + "/" + endpoint + "?" + urlencode(parameters)
        resource = Resource(
            "transferegov-" + hash_content(url),
            endpoint,
            url,
            endpoint,
            datetime.now(UTC).year,
            "transferegov-" + module,
            file_suffix=".json",
        )
        return download_resource(resource, self.configuration, self.client, self.budget)

    def pages(self, module, endpoint, filters):
        query = partition_query(module, endpoint, filters)
        for page_number in range(1, self.configuration.max_pages + 1):
            artifact = self.acquire(module, endpoint, query, page_number)
            try:
                document = json.loads(artifact.path.read_bytes(), parse_float=Decimal)
            except (ValueError, UnicodeError) as error:
                raise IngestionError("TRANSFEREGOV_INVALID_JSON") from error
            validate_page(document, page_number, self.configuration.page_size)
            yield document["data"], artifact
            if page_number >= document["total_pages"]:
                return
        raise IngestionError("TRANSFEREGOV_PAGE_LIMIT_EXCEEDED")
