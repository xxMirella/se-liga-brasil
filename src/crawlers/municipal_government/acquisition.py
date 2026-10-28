"""Immutable municipal-government evidence using shared official-source pacing."""

from dataclasses import dataclass
from pathlib import Path

from service.acquisition.downloader import download_resource
from service.acquisition.http_client import OfficialHttpClient
from service.ingestion.contracts import DownloadBudget, Resource
from storage.files import hash_content

OFFICIAL_HOSTS = frozenset(
    {
        "legislacao.prefeitura.sp.gov.br",
        "www.saopaulo.sp.leg.br",
        "diariooficial.prefeitura.sp.gov.br",
        "www.rio.rj.gov.br",
        "rio.rj.gov.br",
        "www0.rio.rj.gov.br",
        "siurblab.rio.rj.gov.br",
        "prefeitura.rio",
        "www.camara.rio",
        "camara.rio",
        "www.curitiba.pr.gov.br",
        "fortalezaembairros.fortaleza.ce.gov.br",
        "prefeitura.pbh.gov.br",
    }
)


@dataclass(frozen=True)
class MunicipalGovernmentConfiguration:
    storage_directory: Path
    max_download_bytes: int = 12 * 1024**2
    max_run_download_bytes: int = 128 * 1024**2
    request_timeout_seconds: int = 45
    max_attempts: int = 2
    force_recheck_after_hours: int = 168
    request_min_interval_seconds: float = 1.5


class MunicipalGovernmentAcquisition:
    def __init__(self, configuration, http_client):
        self.configuration = configuration
        self.client = OfficialHttpClient(configuration, http_client, OFFICIAL_HOSTS)
        self.budget = DownloadBudget()

    def acquire(self, url, uf, file_suffix=".html"):
        resource = Resource(
            "municipal-government-" + hash_content(url),
            "municipal_government_history",
            url,
            "municipal_government_history",
            2000,
            "municipal-government-history",
            uf,
            file_suffix,
        )
        return download_resource(resource, self.configuration, self.client, self.budget)
