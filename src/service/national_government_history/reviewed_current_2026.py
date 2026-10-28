"""Reviewed excerpts of official election reporting explicitly identify existing office holders.

Election victory alone is insufficient. Sources below say current governor or re-elected;
the latter documents an existing exercise and is not used to invent exercise in 2027.
"""

from service.national_government_history.current_2026 import CURRENT_2026_OBSERVATIONS
from service.national_government_history.party_2026 import (
    PARTY_2026_OBSERVATIONS,
    PARTY_STATEMENT_URLS,
    qualify_party_statement,
)
from service.national_government_history.reviewed_legal_observations import reviewed_office_record

REVIEWED_UNAVAILABLE_PAGES = {
    "https://agenciadenoticias.ms.gov.br/governo-ms/",
    "https://seinf.portal.ap.gov.br/noticia_ler.php?slug=2905%2Fnovo-cartao-postal-de-"
    "macapa-governador-clecio-apresenta-parque-residencia-em-visita-guiada-com-a-imprensa",
}


def reviewed_2026_fallback(storage, failure_urls):
    records = []
    for uf, name, political_party, observed, published, kind, url, locators in (
        (*CURRENT_2026_OBSERVATIONS, *PARTY_2026_OBSERVATIONS)
    ):
        reviewed_source = "/comunicacao/noticias/2026/Outubro/" in url or (
            "www.al.rn.leg.br/noticia/33796/" in url
        ) or url in REVIEWED_UNAVAILABLE_PAGES or url in PARTY_STATEMENT_URLS
        if url not in failure_urls or not reviewed_source:
            continue
        record = reviewed_office_record(
            storage, uf=uf, name=name, text="\n".join(locators), url=url,
            observed=observed, published=published, kind=kind, political_party=political_party,
        )
        records.append(qualify_party_statement(record) if url in PARTY_STATEMENT_URLS else record)
    return records
