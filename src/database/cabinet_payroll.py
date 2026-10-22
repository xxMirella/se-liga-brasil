"""Read versioned cabinet cost facts; employee identities never enter the public projection."""


def fetch_verified_senate_people(connection):
    return connection.execute(
        """SELECT DISTINCT ON (p.id) p.id::text AS person_id,
          f.normalized_value->>'civilName' AS civil_name,f.source_record_id
        FROM se_liga_brasil.person p
        JOIN se_liga_brasil.person_fact f ON f.person_id=p.id
        WHERE f.field_name LIKE 'senado_profile:%%' AND f.review_status='verified'
          AND (f.normalized_value->>'birthDate')::date=p.birth_date
          AND NOT EXISTS(SELECT 1 FROM se_liga_brasil.person_identity_alias a
            WHERE a.alias_person_id=p.id)
        ORDER BY p.id,f.id DESC"""
    ).fetchall()


def fetch_cabinet_payroll_history(connection, person_id, as_of):
    rows = connection.execute(
        """SELECT DISTINCT ON (f.normalized_value->>'period')
          f.normalized_value - 'personId' AS payroll
        FROM se_liga_brasil.person_fact f
        JOIN se_liga_brasil.source_record r ON r.id=f.source_record_id
        WHERE f.person_id=%s::uuid AND f.field_name LIKE 'senado_cabinet_payroll:%%'
          AND f.review_status='verified' AND f.normalized_value->>'period'<=%s
        ORDER BY f.normalized_value->>'period' DESC,r.fetched_at DESC,
          coalesce((f.normalized_value->>'calculationVersion')::int,1) DESC,f.id DESC
        LIMIT 121""",
        (person_id, as_of.strftime("%Y-%m")),
    ).fetchall()
    return {"months": [row["payroll"] for row in rows[:120]], "truncated": len(rows) > 120}
