"""Immutable state-government evidence using shared official-source pacing."""

from dataclasses import dataclass
from pathlib import Path

from service.acquisition.downloader import download_resource
from service.acquisition.http_client import OfficialHttpClient
from service.ingestion.contracts import DownloadBudget, Resource
from storage.files import hash_content

OFFICIAL_HOSTS = frozenset(
    {
        "www3.al.sp.gov.br",
        "www.al.ma.leg.br",
        "www.subsecmilitar.rj.gov.br",
        "www2.alerj.rj.gov.br",
        "www.al.sp.gov.br",
        "al.sp.gov.br",
        "www.sp.gov.br",
        "www.ipea.gov.br",
        "portalantigo.ipea.gov.br",
        "www.bibliotecajuridica.sp.gov.br",
        "www.saopaulo.sp.gov.br",
        "www.agenciasp.sp.gov.br",
        "www.alerj.rj.gov.br",
        "www.rj.gov.br",
        "detran.rj.gov.br",
        "www.tjrj.jus.br",
        "www.defensoria.rj.def.br",
        "www12.senado.leg.br",
        "www.camara.leg.br",
        "www.tse.jus.br",
        "www.tre-rj.jus.br",
        "agenciabrasil.ebc.com.br",
        "www.gov.br",
        "noticias.stf.jus.br",
        "palaciopiratini.rs.gov.br",
        "www.casacivil.pr.gov.br",
        "www.mg.gov.br",
        "goias.gov.br",
        "www.sad.pe.gov.br",
    }
)


@dataclass(frozen=True)
class StateGovernmentConfiguration:
    storage_directory: Path
    max_download_bytes: int = 12 * 1024**2
    max_run_download_bytes: int = 128 * 1024**2
    request_timeout_seconds: int = 45
    max_attempts: int = 2
    force_recheck_after_hours: int = 168
    request_min_interval_seconds: float = 1.5


class StateGovernmentAcquisition:
    def __init__(self, configuration, http_client):
        self.configuration = configuration
        self.client = OfficialHttpClient(configuration, http_client, OFFICIAL_HOSTS)
        self.budget = DownloadBudget()

    def acquire(self, url, uf, file_suffix=".html"):
        resource = Resource(
            "state-government-" + hash_content(url),
            "state_government_history",
            url,
            "state_government_history",
            2000,
            "state-government-history",
            uf,
            file_suffix,
        )
        return download_resource(resource, self.configuration, self.client, self.budget)
