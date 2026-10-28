"""Use the same legislature-scoped verbose roster used by the official SAPL interface."""

import json
from datetime import date

from service.ingestion.contracts import IngestionError


def select_current_legislature(payload, reference):
    document = json.loads(payload)
    rows = document.get("results", []) if isinstance(document, dict) else document
    current = [
        row
        for row in rows
        if date.fromisoformat(row["data_inicio"])
        <= reference
        <= date.fromisoformat(row["data_fim"])
    ]
    if len(current) != 1:
        raise IngestionError("SAPL_CURRENT_LEGISLATURE_AMBIGUOUS")
    return str(current[0]["id"])


def collect_current_roster(acquisition, base_url, reference):
    legislature = acquisition.acquire(
        base_url + "/api/parlamentares/legislatura/?get_all=true", "assembly_legislature", ".json"
    )
    identifier = select_current_legislature(legislature.path.read_bytes(), reference)
    url = base_url + f"/api/parlamentares/legislatura/{identifier}/parlamentares/?get_all=true"
    roster = acquisition.acquire(url, "assembly_roster", ".json")
    return roster, legislature


def parse_current_roster(payload):
    document = json.loads(payload)
    rows = document.get("results", []) if isinstance(document, dict) else document
    if not isinstance(rows, list) or not rows or len(rows) > 200:
        raise IngestionError("SAPL_CURRENT_ROSTER_SCHEMA_CHANGED")
    if isinstance(document, dict) and document.get("next"):
        raise IngestionError("SAPL_CURRENT_ROSTER_PAGINATION_INCOMPLETE")
    members = []
    for row in rows:
        if row.get("ativo") is not True:
            continue
        political_party = row.get("partido")
        if political_party is not None and not isinstance(political_party, str):
            raise IngestionError("SAPL_CURRENT_ROSTER_PARTY_SCHEMA_CHANGED")
        members.append(
            {
                "provider_subject_id": str(row["id"]),
                "name": row["nome_parlamentar"],
                "political_party": political_party,
                "official_url": row.get("url"),
            }
        )
    if not members:
        raise IngestionError("SAPL_CURRENT_ROSTER_NO_ACTIVE_MEMBERS")
    return members
