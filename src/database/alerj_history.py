"""Expose only verified, canonical ALERJ narratives with their exact source pages."""


def fetch_person_historical_activity(connection, person_id, as_of):
    rows = connection.execute(
        """WITH latest AS (SELECT DISTINCT ON (field_name) normalized_value
        FROM se_liga_brasil.person_fact
        WHERE person_id=se_liga_brasil.canonical_person_id(%s::uuid)
          AND field_name LIKE 'alerj_historical_activity:%%' AND review_status='verified'
          AND normalized_value->>'occurredOn'<=%s
        ORDER BY field_name,source_record_id DESC)
        SELECT normalized_value FROM latest
        ORDER BY normalized_value->>'occurredOn' DESC LIMIT 1001""",
        (person_id, as_of.isoformat()),
    ).fetchall()
    items = [public_historical_event(row["normalized_value"]) for row in rows[:1000]]
    items.sort(key=lambda item: (item["occurred_on"], item["action_id"]), reverse=True)
    return {"items": items, "truncated": len(rows) > 1000, "coverage": "partial_official_synopsis"}


def public_historical_event(record):
    proposition = record.get("matter") or {"title": "Registro da atividade parlamentar"}
    return {
        "action_type": "historical_activity",
        "event_type": record["eventType"],
        "action_id": record["eventKey"],
        "occurred_on": record["occurredOn"],
        "date_precision": "day",
        "subject": record["description"],
        "short_description": record["description"],
        "official_url": record["evidenceUrl"],
        "institution": {"code": "alerj", "name": "Assembleia Legislativa do Rio de Janeiro"},
        "proposition": proposition | {"official_key": record["evidenceUrl"]},
        "nominal_ballot_verified": False,
    }
