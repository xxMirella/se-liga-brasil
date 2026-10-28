"""Archive official annual reports and reject HTML security pages masquerading as PDF."""

import json
import re
import subprocess
from html.parser import HTMLParser
from urllib.parse import urljoin

from service.acquisition.downloader import download_resource
from service.ingestion.contracts import Resource

REPORT_CATALOG = "https://www25.senado.leg.br/web/atividade/relatorio-da-presidencia/1999-em-diante"
REPORT_HOSTS = frozenset({"www25.senado.leg.br"})


class AnnualReportCatalogParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.reports = {}

    def handle_starttag(self, tag, attributes):
        if tag != "a":
            return
        url = urljoin(REPORT_CATALOG, dict(attributes).get("href", ""))
        year = re.search(r"/RAP(\d{4})(?:/|$)", url)
        if year and url.startswith("https://www25.senado.leg.br/documents/"):
            self.reports[int(year[1])] = url


def acquire_annual_report(url, year, configuration, client, budget):
    resource = Resource(f"senate-annual-report-{year}", str(year), url,
                        "annual_composition", year, "senate-reports", "BR", ".pdf")
    artifact = download_resource(resource, configuration, client, budget)
    with artifact.path.open("rb") as stream:
        if stream.read(5) != b"%PDF-":
            raise ValueError("SENATE_REPORT_IS_NOT_PDF_POSSIBLE_SECURITY_CHALLENGE")
    return artifact


def extract_annual_report_text(path):
    result = subprocess.run(
        ["pdftotext", "-f", "1", "-l", "120", "-layout", str(path), "-"],
        check=True, capture_output=True, timeout=120,
    )
    return result.stdout.decode("utf-8")


def acquire_report_catalog(configuration, client, budget):
    resource = Resource("senate-report-catalog", "catalog", REPORT_CATALOG,
                        "annual_composition", 0, "senate-reports", "BR", ".html")
    catalog = download_resource(resource, configuration, client, budget)
    parser = AnnualReportCatalogParser()
    parser.feed(catalog.path.read_text())
    return parser.reports


def acquire_modern_report_catalog(configuration, client, budget):
    url = "https://www25.senado.leg.br/web/atividade/relatorio-da-presidencia"
    resource = Resource("senate-current-report-catalog", "catalog", url,
                        "annual_composition", 0, "senate-reports", "BR", ".html")
    catalog = download_resource(resource, configuration, client, budget)
    match = re.search(r'const jsonUrl = "(https://www25.senado.leg.br/documents/[^" ]+)"',
                      catalog.path.read_text())
    if not match:
        raise ValueError("SENATE_REPORT_MODERN_CATALOG_URL_NOT_FOUND")
    resource = Resource("senate-unified-report-catalog", "catalog", match[1],
                        "annual_composition", 0, "senate-reports", "BR", ".json")
    artifact = download_resource(resource, configuration, client, budget)
    data = json.loads(artifact.path.read_bytes())
    return {int(year): secure_report_url(row["pdf"]) for year, row in data.items()}


def secure_report_url(url):
    if url.startswith("http://www25.senado.leg.br/"):
        return "https://" + url.removeprefix("http://")
    return url
