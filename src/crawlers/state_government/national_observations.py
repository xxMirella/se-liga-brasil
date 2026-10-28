"""Bounded official inauguration evidence; observations never imply an entire mandate."""

import re
import subprocess
import unicodedata

from crawlers.state_government.acquisition import (
    OFFICIAL_HOSTS,
    StateGovernmentAcquisition,
)
from service.acquisition.http_client import OfficialHttpClient
from service.ingestion.contracts import IngestionError

NATIONAL_HOSTS = OFFICIAL_HOSTS | {
    "auniao.pb.gov.br", "www.alesc.sc.gov.br", "www.agenciaminas.mg.gov.br",
    "www.al.rn.leg.br", "www.defensoria.ce.def.br", "pddi.secid.ma.gov.br",
    "portal.al.go.leg.br", "www.al.pi.leg.br", "www.assembleia.pr.leg.br",
    "al.se.leg.br", "www.secom.mt.gov.br", "www.pc.ms.gov.br",
    "www.al.al.leg.br", "www.es.gov.br",
    "imperatriz.ma.gov.br",
    "www.cl.df.gov.br", "al.rr.leg.br", "www.sefaz.am.gov.br",
    "www.al.mt.gov.br", "agenciadenoticias.ms.gov.br", "estado.rs.gov.br",
    "www.almg.gov.br", "al.ms.gov.br",
    "www.tre-ba.jus.br", "goias.gov.br", "www.alepa.pa.gov.br", "noticias.stf.jus.br",
    "www.al.ro.leg.br", "www3.estado.rs.gov.br", "seplan.ma.gov.br",
    "seinf.portal.ap.gov.br", "portonacional.to.gov.br", "escriba.camara.leg.br",
    "psd.org.br", "progressistas.org.br", "uniaobrasil.org.br", "portal.rr.gov.br",
}


class NationalGovernmentAcquisition(StateGovernmentAcquisition):
    def __init__(self, configuration, http_client):
        super().__init__(configuration, http_client)
        self.client = OfficialHttpClient(configuration, http_client, NATIONAL_HOSTS)


def comparable_text(text):
    """Ignore newspaper line-break hyphens and missing PDF word spaces, not letters."""
    decomposed = unicodedata.normalize("NFKD", text).casefold()
    return re.sub(r"[^a-z0-9]", "", decomposed)


def require_locators(text, locators):
    normalized = comparable_text(text)
    for locator in locators:
        if comparable_text(locator) not in normalized:
            raise IngestionError(
                "OFFICIAL_GOVERNOR_OBSERVATION_SOURCE_CHANGED", {"locator": locator},
            )


def newspaper_text(path):
    with path.open("rb") as source:
        if source.read(5) != b"%PDF-":
            raise IngestionError("GOVERNOR_NEWSPAPER_NOT_PDF")
    result = subprocess.run(
        ["pdftotext", "-raw", str(path), "-"], capture_output=True, check=True, timeout=30,
    )
    return result.stdout.decode("utf-8")
