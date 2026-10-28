"""Archive and normalize official historical election observations without term inference."""

import json
from pathlib import Path

import httpx

from crawlers.senado.election_catalog import parse_senate_election_catalog
from crawlers.senado.election_history import parse_senate_election_history
from crawlers.senado.historical_acquisition import SenateHistoryConfiguration
from service.acquisition.downloader import download_resource
from service.acquisition.http_client import OfficialHttpClient
from service.ingestion.contracts import DownloadBudget, Resource
from storage.files import save_json

CATALOG_BASE = "https://www12.senado.leg.br/noticias/infomaterias/destaques/infomateria/pagina/"


def discover_election_pages(configuration, official_client, budget):
    pages = {}
    for page in (1, 2):
        url = CATALOG_BASE + str(page)
        resource = Resource("senate-election-catalog-" + str(page), "catalog", url,
                            "historical_elections", 0, "senate-elections", "BR", ".html")
        artifact = download_resource(resource, configuration, official_client, budget)
        pages.update(parse_senate_election_catalog(artifact.path.read_text()))
    if len(pages) != 27:
        raise ValueError("SENATE_ELECTION_CATALOG_REQUIRES_ALL_27_TERRITORIES")
    return pages


def collect_election_page(territory, url, configuration, official_client, budget):
    resource = Resource("senate-elections-" + territory, territory, url,
                        "historical_elections", 0, "senate-elections", territory, ".html")
    artifact = download_resource(resource, configuration, official_client, budget)
    evidence = {"url": url, "sha256": artifact.sha256, "fetched_at": artifact.fetched_at}
    rows = parse_senate_election_history(artifact.path.read_text(), territory, evidence)
    if not rows:
        raise ValueError("SENATE_ELECTION_PAGE_HAS_NO_RECORDS")
    return rows


def main():
    configuration = SenateHistoryConfiguration(Path("data/senate-elections"))
    records = []
    budget = DownloadBudget()
    with httpx.Client(timeout=60) as client:
        official = OfficialHttpClient(configuration, client, frozenset({"www12.senado.leg.br"}))
        pages = discover_election_pages(configuration, official, budget)
        for territory, url in sorted(pages.items()):
            rows = collect_election_page(territory, url, configuration, official, budget)
            records.extend(rows)
            print(json.dumps({"territory": territory, "records": len(rows)}), flush=True)
    save_json(configuration.storage_directory / "historical-election-observations.json", {
        "schema_version": "historical_senate_elections.v1", "observations": records,
        "semantics": "Election-year party labels, not continuous affiliation or seat snapshots",
    })


if __name__ == "__main__":
    main()
