"""Current exercise and party come from the common official ALESP roster."""

from crawlers.alesp.identity import parse_identity_roster
from service.ingestion.contracts import IngestionError


def parse_current_roster(payload):
    rows = parse_identity_roster(payload)
    if any(row.get("Situacao") != "EXE" for row in rows):
        raise IngestionError("ALESP_ROSTER_CONTAINS_NON_EXERCISING_MEMBERS")
    return [
        {
            "provider_subject_id": row["IdDeputado"],
            "name": row["NomeParlamentar"],
            "political_party": row.get("Partido"),
            "official_url": "https://www.al.sp.gov.br/deputado/?matricula=" + row["Matricula"],
        }
        for row in rows
    ]
