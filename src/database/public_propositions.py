"""Bounded, dated authorship projection linked to canonical people."""


def fetch_person_propositions(connection, person_id, as_of, page=1):
    if type(page) is not int or not 1 <= page <= 1000:
        raise ValueError("Invalid proposition page")
    rows = connection.execute(
        """SELECT p.id,p.title,p.kind,p.introduced_on,p.summary,p.official_key,
          i.name AS institution,array_agg(DISTINCT link.role) AS roles
        FROM se_liga_brasil.proposition_person link
        JOIN se_liga_brasil.proposition p ON p.id=link.proposition_id
        JOIN se_liga_brasil.institution i ON i.id=p.institution_id
        WHERE link.person_id=%s AND (p.introduced_on IS NULL OR p.introduced_on<=%s)
        GROUP BY p.id,i.name ORDER BY p.introduced_on DESC NULLS LAST,p.id DESC
        LIMIT 101 OFFSET %s""",
        (person_id, as_of, (page - 1) * 100),
    ).fetchall()
    return {"items": [
        {"id": row["id"], "title": row["title"], "kind": row["kind"],
         "occurred_on": row["introduced_on"].isoformat() if row["introduced_on"] else None,
         "date_precision": "day" if row["introduced_on"] else "unknown",
         "summary": row["summary"], "official_url": row["official_key"],
         "institution": row["institution"], "roles": row["roles"]}
        for row in rows[:100]
    ], "truncated": len(rows) > 100, "page": page,
        "coverage": "recorded_authorship_only"}
