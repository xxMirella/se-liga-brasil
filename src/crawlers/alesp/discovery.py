"""Discover published payroll months from the official index, never invented URLs."""

import hashlib
import re
from datetime import UTC, datetime
from urllib.parse import urljoin, urlsplit

from crawlers.alesp.configuration import OFFICIAL_HOSTS, PAYROLL_INDEX_URL
from parsing.html import HtmlLinksParser, decode_html
from service.acquisition.http_client import validate_official_url
from service.ingestion.contracts import IngestionError, Resource
from storage.files import save_json, write_private_bytes

PAYROLL_PATH = re.compile(
    r"/repositorio/folha-de-pagamento/folha-deputados-(20\d{2})-(\d{2})\.html$"
)


def payroll_month(resource: Resource) -> str:
    return resource.resource_id.removeprefix("alesp-deputy-payroll-")


def is_selected_resource(resource: Resource, configuration) -> bool:
    return (not configuration.years or resource.year in configuration.years) and (
        not configuration.months or payroll_month(resource) in configuration.months
    )


def parse_payroll_resources(payload: bytes) -> list[Resource]:
    parser = HtmlLinksParser()
    parser.feed(decode_html(payload))
    resources = {}
    for link in parser.links:
        url = urljoin(PAYROLL_INDEX_URL, link)
        match = PAYROLL_PATH.fullmatch(urlsplit(url).path)
        if not match:
            continue
        validate_official_url(url, OFFICIAL_HOSTS)
        month = f"{match[1]}-{match[2]}"
        if not 1 <= int(match[2]) <= 12:
            raise IngestionError("INVALID_PAYROLL_MONTH")
        resources[month] = Resource(
            f"alesp-deputy-payroll-{month}",
            f"ALESP folha {month}",
            url,
            "deputy_payroll",
            int(match[1]),
            "alesp-deputy-payroll",
            "SP",
            file_suffix=".html",
        )
    return [resources[month] for month in sorted(resources)]


def discover_resources(configuration, client) -> list[Resource]:
    payload = client.fetch_bytes(PAYROLL_INDEX_URL, configuration.max_download_bytes)
    digest = hashlib.sha256(payload).hexdigest()
    path = configuration.storage_directory / "catalogs" / f"{digest}.html"
    write_private_bytes(path, [payload])
    save_json(
        configuration.storage_directory / "catalog-manifest.json",
        {
            "url": PAYROLL_INDEX_URL,
            "sha256": digest,
            "path": str(path),
            "fetched_at": datetime.now(UTC).isoformat(),
        },
    )
    resources = [
        item
        for item in parse_payroll_resources(payload)
        if is_selected_resource(item, configuration)
    ]
    if not resources:
        raise IngestionError("NO_PUBLISHED_PAYROLL_RESOURCES")
    return resources
