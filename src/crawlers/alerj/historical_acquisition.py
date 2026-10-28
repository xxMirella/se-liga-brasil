"""Replay verified ALERJ archives offline, and discover only linked synopsis PDFs."""

import re
from datetime import UTC, datetime
from urllib.parse import urljoin, urlsplit

from crawlers.alerj.acquisition import AlerjAcquisition
from crawlers.alerj.configuration import OFFICIAL_HOSTS
from crawlers.alerj.parsing import parse_page
from service.acquisition.downloader import (
    build_downloaded_artifact,
    download_resource,
    is_cached_archive_intact,
)
from service.acquisition.http_client import validate_official_url
from service.ingestion.contracts import IngestionError, Resource
from storage.files import hash_content, load_json


def historical_resource(url, kind, suffix):
    validate_official_url(url, OFFICIAL_HOSTS)
    match = re.search(r"_(\d{4})\.pdf$", url, re.I)
    year = int(match[1]) if match else datetime.now(UTC).year
    return Resource(
        "alerj-" + hash_content(url),
        kind,
        url,
        kind,
        year,
        "alerj-enrichment",
        "RJ",
        suffix,
    )


class AlerjHistoryAcquisition(AlerjAcquisition):
    def acquire(self, url, kind, suffix=".html"):
        return download_resource(
            historical_resource(url, kind, suffix), self.configuration, self.client, self.budget
        )


class CachedAlerjHistoryAcquisition:
    def __init__(self, configuration):
        self.configuration = configuration

    def acquire(self, url, kind, suffix=".html"):
        resource = historical_resource(url, kind, suffix)
        manifest = load_json(
            self.configuration.storage_directory / "manifests" / f"{resource.resource_id}.json"
        )
        if not is_cached_archive_intact(manifest, resource):
            raise IngestionError("ALERJ_OFFLINE_ARCHIVE_MISSING_OR_CHANGED")
        return build_downloaded_artifact(resource, manifest, "cached")


def discover_synopsis_documents(payload, catalog_url, *, limit=10):
    if type(limit) is not int or not 1 <= limit <= 50:
        raise ValueError("Invalid synopsis document limit")
    validate_official_url(catalog_url, OFFICIAL_HOSTS)
    documents = {}
    for href, _ in parse_page(payload).links:
        url = urljoin(catalog_url, href)
        if urlsplit(url).path.casefold().endswith(".pdf"):
            validate_official_url(url, OFFICIAL_HOSTS)
            documents[url] = None
    return list(documents)[:limit]
