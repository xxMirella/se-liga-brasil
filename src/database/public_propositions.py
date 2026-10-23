"""Bounded, dated authorship projection linked to canonical people."""

import re

CAMARA_DOCUMENT_URL = re.compile(r"https://dadosabertos\.camara\.leg\.br/api/v2/proposicoes/([1-9][0-9]*)")


def fetch_person_propositions(connection, person_id, as_of, page=1):
    if type(page) is not int or not 1 <= page <= 1000:
        raise ValueError("Invalid proposition page")
    rows = connection.execute(
        """SELECT p.id,p.title,p.kind,p.number,p.year,p.introduced_on,p.summary,p.official_key,
          i.name AS institution,i.code AS institution_code,
          detail.normalized_data->>'principalProposition' AS principal_key,
          parent.title AS principal_title,parent.kind AS principal_kind,
          parent.number AS principal_number,parent.year AS principal_year,
          array_agg(DISTINCT link.role) AS roles,
          (SELECT coalesce(jsonb_agg(item),'[]'::jsonb) FROM (
            SELECT e.official_event_key,e.occurred_at,e.event_type,e.description,
              (e.occurred_at AT TIME ZONE 'America/Belem')::date AS occurred_on
            FROM se_liga_brasil.proposition_event e WHERE e.proposition_id=p.id
              AND (e.occurred_at AT TIME ZONE 'America/Belem')::date<=%s
            ORDER BY e.occurred_at DESC,e.id DESC LIMIT 101) item) AS events
        FROM se_liga_brasil.proposition_person link
        JOIN se_liga_brasil.proposition p ON p.id=link.proposition_id
        JOIN se_liga_brasil.institution i ON i.id=p.institution_id
        LEFT JOIN se_liga_brasil.source source ON source.code=i.code
        LEFT JOIN se_liga_brasil.ingestion_entity detail ON detail.source_id=source.id
          AND detail.entity_kind='camara_legislative_detail'
          AND detail.external_key='detail:'||p.official_key
        LEFT JOIN se_liga_brasil.proposition parent ON parent.institution_id=p.institution_id
          AND parent.official_key=detail.normalized_data->>'principalProposition'
        WHERE link.person_id=%s AND (p.introduced_on IS NULL OR p.introduced_on<=%s)
        GROUP BY p.id,i.name,i.code,detail.id,parent.id
        ORDER BY p.introduced_on DESC NULLS LAST,p.id DESC
        LIMIT 101 OFFSET %s""",
        (as_of, person_id, as_of, (page - 1) * 100),
    ).fetchall()
    return {"items": [
        {"id": row["id"], "title": row["title"], "kind": row["kind"],
         "occurred_on": row["introduced_on"].isoformat() if row["introduced_on"] else None,
         "date_precision": "day" if row["introduced_on"] else "unknown",
         "summary": row["summary"], "official_url": row["official_key"],
         "official_key": row["official_key"], "number": row.get("number"),
         "year": row.get("year"), "institution_code": row.get("institution_code"),
         "official_parent": public_official_parent(row),
         "document_label": public_document_label(row),
         "events": (row.get("events") or [])[:100],
         "events_truncated": len(row.get("events") or []) > 100,
         "institution": row["institution"], "roles": row["roles"]}
        for row in rows[:100]
    ], "truncated": len(rows) > 100, "page": page,
        "coverage": "recorded_authorship_only"}


def public_official_parent(row):
    principal_key = row.get("principal_key")
    if row.get("institution_code") != "camara" or not principal_key:
        return None
    if not isinstance(principal_key, str) or not CAMARA_DOCUMENT_URL.fullmatch(principal_key):
        return None
    if principal_key == row["official_key"]:
        return None
    return {
        "institution_code": "camara", "official_key": principal_key,
        "title": row.get("principal_title"), "kind": row.get("principal_kind"),
        "number": row.get("principal_number"), "year": row.get("principal_year"),
    }


def public_document_label(row):
    if row.get("institution_code") != "camara" or row.get("year") is not None:
        return None
    identifier = CAMARA_DOCUMENT_URL.fullmatch(row["official_key"])
    if identifier is None:
        return None
    return "Documento Câmara " + identifier[1]
