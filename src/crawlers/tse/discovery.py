"""Discover official resources through the TSE CKAN catalog."""

import re
from datetime import UTC, datetime
from urllib.parse import urlsplit

from crawlers.tse.configuration import CATALOG_API, CrawlerConfiguration
from crawlers.tse.http_client import OfficialHttpClient, validate_official_url
from service.ingestion.contracts import RESOURCE_KINDS, Resource
from storage.files import save_json

RESOURCE_PATTERNS = {
    "candidate": r"/consulta_cand/consulta_cand_\d{4}\.zip$",
    "history": r"/historico_candidatura/",
    "complement": r"/consulta_cand_complementar/",
    "asset": r"/bem_candidato/",
    "government_proposal": r"/proposta_governo/",
    "criminal_certificate": r"/certidao_criminal/",
}


def classify_resource(url: str) -> str | None:
    path = urlsplit(url).path
    return next(
        (kind for kind, pattern in RESOURCE_PATTERNS.items() if re.search(pattern, path)), None
    )


def select_resources(dataset: dict, configuration: CrawlerConfiguration) -> list[Resource]:
    match = re.fullmatch(r"candidatos-(\d{4})", dataset["name"])
    if not match:
        return []
    resources = []
    for metadata in dataset["resources"]:
        resource = build_resource(metadata, dataset["name"], int(match[1]))
        if resource and is_selected_resource(resource, configuration):
            resources.append(resource)
    return resources


def build_resource(metadata: dict, dataset: str, year: int) -> Resource | None:
    resource_url = metadata["url"].strip().removeprefix("URL: ")
    kind = classify_resource(resource_url)
    if kind is None:
        return None
    validate_official_url(resource_url)
    if not re.fullmatch(r"[a-zA-Z0-9-]+", metadata["id"]):
        return None
    uf_match = re.search(r"_([A-Z]{2})\.zip$", resource_url)
    return Resource(
        metadata["id"],
        metadata["name"],
        resource_url,
        kind,
        year,
        dataset,
        uf_match[1] if uf_match else None,
    )


def is_selected_resource(resource: Resource, configuration: CrawlerConfiguration) -> bool:
    if resource.kind not in configuration.kinds:
        return False
    return not resource.uf or not configuration.ufs or resource.uf in configuration.ufs


def discover_dataset_names(
    configuration: CrawlerConfiguration, client: OfficialHttpClient
) -> list[str]:
    if configuration.years:
        return [f"candidatos-{year}" for year in configuration.years]
    names = []
    start = 0
    while True:
        page = client.fetch_catalog(
            f"{CATALOG_API}package_search?fq=groups:candidatos&rows=100&start={start}"
        )
        names.extend(
            dataset["name"]
            for dataset in page["results"]
            if re.fullmatch(r"candidatos-\d{4}", dataset["name"])
        )
        start += 100
        if start >= page["count"]:
            return names


def discover_resources(
    configuration: CrawlerConfiguration, client: OfficialHttpClient
) -> list[Resource]:
    resources = []
    for dataset_name in discover_dataset_names(configuration, client):
        dataset = client.fetch_catalog(f"{CATALOG_API}package_show?id={dataset_name}")
        save_json(
            configuration.storage_directory / "catalogs" / f"{dataset_name}.json",
            {
                "fetched_at": datetime.now(UTC).isoformat(),
                "dataset": dataset,
            },
        )
        resources.extend(select_resources(dataset, configuration))
    priorities = {kind: index for index, kind in enumerate(RESOURCE_KINDS)}
    return sorted(
        resources,
        key=lambda resource: (-resource.year, priorities[resource.kind], resource.resource_id),
    )
