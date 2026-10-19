"""Select existing shared documents without one query per person or proposition."""


def select_proposition_keys(
    connection, institution, person_ids=None, *, limit=25, start=None, end=None
):
    if not 1 <= limit <= 100:
        raise ValueError("Proposition batch must contain at most 100 documents")
    return [
        row["official_key"]
        for row in connection.execute(
            """WITH checked AS (
          SELECT source_url,max(fetched_at) AS checked_on
          FROM se_liga_brasil.ingestion_artifact
          WHERE resource_kind='camara_legislative_detail' AND status='completed'
          GROUP BY source_url)
        SELECT p.official_key FROM se_liga_brasil.proposition p
        JOIN se_liga_brasil.institution i ON i.id=p.institution_id
        LEFT JOIN checked ON checked.source_url=p.official_key
        WHERE i.code=%s AND (%s::uuid[] IS NULL OR EXISTS(
          SELECT 1 FROM se_liga_brasil.proposition_person link
          WHERE link.proposition_id=p.id AND link.person_id=ANY(%s::uuid[])))
        AND (%s::date IS NULL OR p.introduced_on BETWEEN %s::date AND %s::date
          OR (p.introduced_on IS NULL AND p.year BETWEEN
            extract(year FROM %s::date) AND extract(year FROM %s::date)))
        ORDER BY checked.checked_on ASC NULLS FIRST,
          p.introduced_on DESC NULLS LAST,p.id DESC LIMIT %s""",
            (institution, person_ids, person_ids, start, start, end, start, end, limit),
        ).fetchall()
    ]
