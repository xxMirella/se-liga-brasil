"""Archive official party directory entries and first listed statutes; no ideology inference."""

import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from crawlers.party_documents.acquisition import PartyDocumentAcquisition
from crawlers.party_documents.links import current_statute_link, parsed_document_links
from service.ingestion.contracts import IngestionError
from storage.files import save_json

DIRECTORY = (
    "https://www.tse.jus.br/partidos/partidos-registrados-no-tse"  # hardcode-ok: fonte oficial
)
TARGETS = frozenset(
    name.casefold()
    for name in (
        "PL",
        "PT",
        "UNIÃO",
        "PSD",
        "PP",
        "REPUBLICANOS",
        "MDB",
        "PODE",
        "PSB",
        "PSDB",
        "PSOL",
        "PCdoB",
        "PDT",
        "PV",
        "AVANTE",
        "NOVO",
        "SOLIDARIEDADE",
        "PRD",
        "REDE",
        "CIDADANIA",
        "DC",
        "MISSÃO",
        "AGIR",
        "MOBILIZA",
        "PSTU",
        "PCB",
        "PRTB",
        "PCO",
        "DEMOCRATA",
        "UP",
    )
)


def collect_party_source(acquisition, link):
    entry = {"political_party": link["text"], "directory_url": link["url"]}
    try:
        entry["directory_archive"] = acquisition.acquire(link["url"])
        content = Path(entry["directory_archive"]["path"]).read_text()
        statute = current_statute_link(content, link["url"])
        if statute:
            entry["statute_listing"] = statute
            entry["statute_archive"] = acquisition.acquire(statute["url"], ".pdf")
            entry["status"] = "archived_pending_substantive_review"
        else:
            entry["status"] = "statute_link_not_found"
    except (IngestionError, ValueError, httpx.TransportError) as error:
        entry.update(status="acquisition_failed", error=str(error))
    return entry


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage", type=Path, default=Path("data/party-documents"))
    options = parser.parse_args()
    with httpx.Client() as client:
        acquisition = PartyDocumentAcquisition(
            options.storage,
            client,
            {
                "www.tse.jus.br",
                "www.justicaeleitoral.jus.br",
            },
        )
        receipt = acquisition.acquire(DIRECTORY)
        links = parsed_document_links(Path(receipt["path"]).read_text(), DIRECTORY)
        selected = {
            link["text"].casefold(): link
            for link in links
            if link["text"].casefold() in TARGETS
            and urlsplit(link["url"]).hostname == "www.tse.jus.br"
        }
        results = []
        for label, link in sorted(selected.items()):
            results.append(collect_party_source(acquisition, link))
            save_json(
                options.storage / "tse-source-inventory.json",
                {
                    "schema_version": "party_documentary_source_inventory.v1",
                    "directory_archive": receipt,
                    "sources": results,
                    "not_located_in_directory": sorted(TARGETS - set(selected)),
                },
            )
            progress = {"political_party": label, "status": results[-1]["status"]}
            print(json.dumps(progress), flush=True)


if __name__ == "__main__":
    main()
