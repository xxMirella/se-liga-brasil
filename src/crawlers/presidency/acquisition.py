"""Bounded official downloads with immutable archives, validators and shared host pacing."""

from dataclasses import dataclass
from pathlib import Path

from service.acquisition.downloader import download_resource
from service.acquisition.http_client import OfficialHttpClient
from service.ingestion.contracts import DownloadBudget, Resource
from storage.files import hash_content

GALLERY_URL = (
    "https://www.gov.br/secretariageral/pt-br/centrais-de-conteudo/"
    "biblioteca-da-pr/galeria-dos-ex-presidentes"
)
SOURCE_HOSTS = frozenset({"www.gov.br", "www.camara.leg.br", "www.al.sp.gov.br",
                            "mapa.arquivonacional.gov.br", "presidentes.an.gov.br",
                            "www.biblioteca.presidencia.gov.br", "www.ce.gov.br",
                            "educapes.capes.gov.br", "www12.senado.leg.br",
                            "www2.camara.leg.br", "www.tse.jus.br",
                            "agenciabrasil.ebc.com.br", "memoriapolitica.alesc.sc.gov.br",
                            "neamp.pucsp.br", "bndigital.bn.gov.br", "repositorio.unb.br",
                            "periodicos.fclar.unesp.br", "files.ufgd.edu.br"})
FIRST_REPUBLIC_URL = "https://www.camara.leg.br/noticias/93698-os-presidentes-da-republica-velha/"


@dataclass(frozen=True)
class PresidencyConfiguration:
    storage_directory: Path
    max_download_bytes: int = 8 * 1024**2
    max_run_download_bytes: int = 64 * 1024**2
    request_timeout_seconds: int = 45
    max_attempts: int = 2
    force_recheck_after_hours: int = 168
    request_min_interval_seconds: float = 1.5


class PresidencyAcquisition:
    def __init__(self, configuration, http_client):
        self.configuration = configuration
        self.client = OfficialHttpClient(configuration, http_client, SOURCE_HOSTS)
        self.budget = DownloadBudget()

    def acquire(self, url, *, file_suffix=".html"):
        resource = Resource(
            "presidency-" + hash_content(url), "presidential_chronology", url,
            "presidential_chronology", 1889, "presidency-history", "BR", file_suffix,
        )
        return download_resource(resource, self.configuration, self.client, self.budget)
