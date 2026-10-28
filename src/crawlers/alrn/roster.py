"""Project dated parliamentary and affiliation records from RN's official transparency API."""

import json
from datetime import date

from service.ingestion.contracts import IngestionError


def valid_on(interval, reference):
    start, end = interval.get("inicio"), interval.get("fim")
    return bool(
        start
        and date.fromisoformat(start[:10]) <= reference
        and (not end or date.fromisoformat(end[:10]) >= reference)
    )


def parse_current_roster(payload, reference=None):
    reference = reference or date.today()
    document = json.loads(payload)
    rows = document.get("dados")
    if not isinstance(rows, list) or len(rows) > 200:
        raise IngestionError("ALRN_PARLIAMENTARY_API_SCHEMA_CHANGED")
    members = []
    for row in rows:
        if not valid_on(row.get("vigencia", {}), reference):
            continue
        affiliations = [
            f for f in row.get("filiacoes", []) if valid_on(f.get("vigencia", {}), reference)
        ]
        if len(affiliations) > 1:
            raise IngestionError("ALRN_SIMULTANEOUS_AFFILIATIONS_AMBIGUOUS")
        party = affiliations[0]["partido"] if affiliations else {}
        members.append(
            {
                "provider_subject_id": str(row["id"]),
                "name": row["nomeParlamentar"].removeprefix("DEPUTADO ").removeprefix("DEPUTADA "),
                "political_party": party.get("sigla") or party.get("nome"),
            }
        )
    if len(members) != 24:
        raise IngestionError("ALRN_CURRENT_REGISTRY_EXPECTED_24_MEMBERS")
    return members
