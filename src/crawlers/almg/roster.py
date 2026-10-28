"""Current exercise comes from the dedicated official endpoint, not electoral returns."""

import json

from service.ingestion.contracts import IngestionError


def parse_current_roster(payload):
    document = json.loads(payload)
    rows = document.get("list")
    if not isinstance(rows, list) or not 1 <= len(rows) <= 150:
        raise IngestionError("ALMG_CURRENT_ROSTER_SCHEMA_CHANGED")
    return [
        {
            "provider_subject_id": str(row["id"]),
            "name": row["nome"],
            "political_party": row.get("partido"),
            "official_url": f"https://www.almg.gov.br/deputados/{row['id']}/",
        }
        for row in rows
    ]
