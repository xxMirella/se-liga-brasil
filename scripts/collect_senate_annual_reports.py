"""Collect the annual-report composition sections with immutable source evidence."""

import argparse
import json
from pathlib import Path

import httpx

from crawlers.senado.annual_reports import (
    REPORT_HOSTS,
    acquire_annual_report,
    acquire_modern_report_catalog,
    acquire_report_catalog,
    extract_annual_report_text,
)
from crawlers.senado.historical_acquisition import SenateHistoryConfiguration
from service.acquisition.http_client import OfficialHttpClient
from service.ingestion.contracts import DownloadBudget
from storage.files import save_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--first-year", type=int, default=1999)
    parser.add_argument("--last-year", type=int, default=2014)
    options = parser.parse_args()
    directory = Path("data/senate-annual-reports")
    configuration = SenateHistoryConfiguration(
        directory, max_download_bytes=50 * 1024**2, max_run_download_bytes=300 * 1024**2,
    )
    budget = DownloadBudget()
    with httpx.Client(timeout=60) as raw:
        client = OfficialHttpClient(configuration, raw, REPORT_HOSTS)
        reports = acquire_report_catalog(configuration, client, budget)
        reports.update(acquire_modern_report_catalog(configuration, client, budget))
        for year, url in sorted(reports.items()):
            if options.first_year <= year <= options.last_year:
                collect_report(year, url, configuration, client, budget)


def collect_report(year, url, configuration, client, budget):
    artifact = acquire_annual_report(url, year, configuration, client, budget)
    content = extract_annual_report_text(artifact.path)
    text_path = configuration.storage_directory / f"{year}-first-120-pages.txt"
    text_path.write_text(content)
    save_json(configuration.storage_directory / f"{year}-evidence.json", {
        "year": year, "url": url, "sha256": artifact.sha256,
        "fetched_at": artifact.fetched_at, "extracted_text_path": str(text_path),
    })
    print(json.dumps({"year": year, "bytes": artifact.bytes_downloaded}), flush=True)


if __name__ == "__main__":
    main()
