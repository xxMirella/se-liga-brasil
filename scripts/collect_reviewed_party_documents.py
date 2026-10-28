"""Archive explicitly reviewed source URLs; never turn retrieved text into ideology labels."""

import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from crawlers.party_documents.acquisition import PartyDocumentAcquisition
from service.ingestion.contracts import IngestionError
from storage.files import load_json, save_json


def collect_reviewed_documents(source_list, storage):
    hosts = {urlsplit(row["url"]).hostname for row in source_list}
    results = load_json(storage / "reviewed-source-receipts.json", [])
    completed = {row["key"] for row in results}
    with httpx.Client(headers={"Accept": "text/html,application/pdf;q=0.9,*/*;q=0.8"}) as client:
        acquisition = PartyDocumentAcquisition(storage, client, hosts)
        for source in source_list:
            if source["key"] in completed:
                continue
            result = dict(source)
            try:
                result["archive"] = acquisition.acquire(
                    source["url"], source.get("suffix", ".html")
                )
                result["status"] = "archived_pending_review"
            except (IngestionError, ValueError, httpx.TransportError) as error:
                result.update(status="acquisition_failed", error=str(error),
                              error_details=getattr(error, "details", {}))
            results.append(result)
            save_json(storage / "reviewed-source-receipts.json", results)
            print(json.dumps({"key": source["key"], "status": result["status"]}), flush=True)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-list", type=Path, required=True)
    parser.add_argument("--storage", type=Path, default=Path("data/party-documents"))
    options = parser.parse_args()
    collect_reviewed_documents(json.loads(options.source_list.read_text()), options.storage)


if __name__ == "__main__":
    main()
