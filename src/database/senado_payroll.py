"""Select canonical people with previously verified official Senate identity evidence."""


def fetch_verified_payroll_profiles(connection, period, limit=100, person_id=None):
    rows = connection.execute(
        """WITH profiles AS (
          SELECT DISTINCT ON (p.id) p.id,f.normalized_value AS profile,
            f.source_record_id,r.source_url,r.content_sha256
          FROM se_liga_brasil.person p
          JOIN se_liga_brasil.person_fact f ON f.person_id=p.id
          JOIN se_liga_brasil.source_record r ON r.id=f.source_record_id
          JOIN se_liga_brasil.source s ON s.id=r.source_id AND s.code='senado'
          WHERE f.field_name LIKE 'senado_profile:%%' AND f.review_status='verified'
            AND f.normalized_value->>'personId'=p.id::text
            AND f.normalized_value->>'birthDate'=p.birth_date::text
            AND f.normalized_value->>'identityMethod' IN
              ('validated_cpf','unique_full_name_birth_date')
            AND (%s::uuid IS NULL OR p.id=%s::uuid)
            AND NOT EXISTS(SELECT 1 FROM se_liga_brasil.person_identity_alias a
              WHERE a.alias_person_id=p.id)
          ORDER BY p.id,r.fetched_at DESC,f.id DESC)
        SELECT profile,source_record_id,source_url,content_sha256 FROM profiles v
        ORDER BY EXISTS(SELECT 1 FROM se_liga_brasil.person_payroll_payment payment
          WHERE payment.person_id=v.id AND payment.organization_code='senado'
            AND payment.competence=%s AND payment.identity_status='verified'),v.id
        LIMIT %s""",
        (person_id, person_id, period, limit),
    ).fetchall()
    return [profile_with_evidence(row) for row in rows]


def profile_with_evidence(row):
    return row["profile"] | {
        "evidence": [
            *row["profile"].get("evidence", []),
            {
                "sourceRecordId": row["source_record_id"],
                "url": row["source_url"],
                "sha256": row["content_sha256"],
            },
        ]
    }
