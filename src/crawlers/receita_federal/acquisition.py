"""Explicit plans prevent national multi-GB downloads by default."""

import re
from urllib.parse import urlsplit

from crawlers.receita_federal.configuration import OFFICIAL_HOSTS
from service.acquisition.downloader import download_resource
from service.acquisition.http_client import validate_official_url
from service.ingestion.contracts import DownloadBudget, IngestionError, Resource
from storage.files import hash_content

PARTITION_PATTERN = re.compile(r"(Empresas|Estabelecimentos|Socios)([0-9])\.zip", re.I)
KINDS = {"empresas": "companies", "estabelecimentos": "establishments", "socios": "partners"}


def plan_resources(snapshot_month, selected_urls, configuration):
    if not re.fullmatch(r"[0-9]{4}-(0[1-9]|1[0-2])", snapshot_month):
        raise IngestionError("CNPJ_INVALID_SNAPSHOT_MONTH")
    resources = {}
    for url in selected_urls:
        validate_official_url(url, OFFICIAL_HOSTS)
        parsed = urlsplit(url)
        match = PARTITION_PATTERN.fullmatch(parsed.path.rsplit("/", 1)[-1])
        if not match or parsed.query or parsed.fragment:
            raise IngestionError("CNPJ_UNSUPPORTED_PARTITION")
        if snapshot_month not in parsed.path.split("/"):
            raise IngestionError("CNPJ_SNAPSHOT_URL_MISMATCH")
        resources[url] = Resource(
            hash_content(url),
            match.group(0),
            url,
            KINDS[match.group(1).lower()],
            int(snapshot_month[:4]),
            snapshot_month,
            None,
            ".zip",
        )
        if len(resources) > configuration.max_resources:
            raise IngestionError("CNPJ_RESOURCE_LIMIT_EXCEEDED")
    return tuple(resources.values())


def acquire_resources(resources, configuration, client):
    resources = tuple(resources)
    if len(resources) > configuration.max_resources:
        raise IngestionError("CNPJ_RESOURCE_LIMIT_EXCEEDED")
    budget = DownloadBudget()
    for resource in resources:
        yield download_resource(resource, configuration, client, budget)
