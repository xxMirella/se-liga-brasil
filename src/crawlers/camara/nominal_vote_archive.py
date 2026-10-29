"""Annual open-data CSV files of Chamber roll calls (votacoes, votos, orientacoes, objects)."""

import httpx

from storage.polite_archive import FetchedFile, PoliteArchive

BULK_BASE = "https://dadosabertos.camara.leg.br/arquivos"
FIRST_YEAR_PROBED = 1991
SMALL_KINDS = ("votacoes", "votacoesProposicoes", "votacoesOrientacoes")
VOTES_KIND = "votacoesVotos"


def annual_file_url(kind: str, year: int) -> str:
    return f"{BULK_BASE}/{kind}/csv/{kind}-{year}.csv"


def annual_file_name(kind: str, year: int) -> str:
    return f"camara/{kind}-{year}.csv"


def fetch_annual_file(archive: PoliteArchive, kind: str, year: int) -> FetchedFile | None:
    """Return the file, or None when the Chamber publishes nothing for that kind and year."""
    name = annual_file_name(kind, year)
    if archive.is_known_unavailable(name):
        return None
    url = annual_file_url(kind, year)
    try:
        return archive.fetch(url, name, year, kind)
    except httpx.HTTPStatusError as error:
        if error.response.status_code == 404:
            archive.record_unavailable(url, name, year, kind, 404)
            return None
        raise
