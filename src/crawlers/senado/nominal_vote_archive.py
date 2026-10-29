"""Annual Senate roll-call archive from the /votacao endpoint (votes embedded per voting)."""

import httpx

from storage.polite_archive import FetchedFile, PoliteArchive

VOTING_ENDPOINT = "https://legis.senado.leg.br/dadosabertos/votacao"


def annual_file_name(year: int) -> str:
    return f"senado/votacao-{year}.json"


def fetch_year(archive: PoliteArchive, year: int) -> FetchedFile | None:
    name = annual_file_name(year)
    if archive.is_known_unavailable(name):
        return None
    params = {"dataInicio": f"{year}-01-01", "dataFim": f"{year}-12-31"}
    try:
        return archive.fetch(VOTING_ENDPOINT, name, year, "senado_votacao", params)
    except httpx.HTTPStatusError as error:
        if error.response.status_code in (404, 400):
            archive.record_unavailable(
                VOTING_ENDPOINT, name, year, "senado_votacao", error.response.status_code
            )
            return None
        raise
