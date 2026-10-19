"""One query checks the canonical people, including people with no electoral records."""


def fetch_completeness_rows(connection, person_id=None) -> list:
    return connection.execute(
        """
        SELECT p.id::text AS person_id,p.civil_name,p.birth_date,p.education_level,
          EXISTS(SELECT 1 FROM se_liga_brasil.political_party_affiliation a
            WHERE a.person_id=p.id AND a.evidence_kind
              IN ('administrative','official_membership')
              AND a.observed_on>=current_date-30
              AND a.information_valid_until IS NULL) AS current_party,
          p.has_current_public_office AS current_office,
          (SELECT max(pay.competence) FROM se_liga_brasil.person_payroll_payment pay
            WHERE pay.person_id=p.id AND pay.identity_status='verified') AS latest_payroll,
          (SELECT max(c.election_year) FROM se_liga_brasil.electoral_candidacy c
            WHERE c.person_id=p.id) AS latest_election,
          (SELECT max(a.election_year) FROM se_liga_brasil.candidate_asset_declaration a
            WHERE a.person_id=p.id) AS latest_assets,
          EXISTS(SELECT 1 FROM se_liga_brasil.person_fact f
            WHERE f.person_id=p.id
            AND f.normalized_value->>'declaresAssets'='false'
            AND (f.normalized_value->>'electionYear')::int=(SELECT max(c.election_year)
                FROM se_liga_brasil.electoral_candidacy c
                WHERE c.person_id=p.id)) AS reported_no_assets,
          EXISTS(SELECT 1 FROM se_liga_brasil.proposition_person pp
            WHERE pp.person_id=p.id) AS has_propositions,
          attendance.period AS latest_attendance_period,attendance.unknown AS attendance_unknown
        FROM se_liga_brasil.person p
        LEFT JOIN LATERAL (
          SELECT ((f.normalized_value->>'period')||'-01')::date AS period,
            coalesce((f.normalized_value->>'unknown')::int,0) AS unknown
          FROM se_liga_brasil.person_fact f
          JOIN se_liga_brasil.institution i ON i.id=p.current_public_office_institution_id
          WHERE f.person_id=p.id AND f.field_name LIKE '%%_attendance:%%'
            AND f.review_status='verified' AND f.normalized_value->>'institution'=i.code
            AND f.normalized_value->>'period'<to_char(timezone('America/Belem',now()),'YYYY-MM')
          ORDER BY f.normalized_value->>'period' DESC,
            f.normalized_value->>'sourceObservedAt' DESC,f.id DESC LIMIT 1
        ) attendance ON true
        WHERE (%s::uuid IS NULL OR p.id=%s::uuid)
          AND NOT EXISTS(SELECT 1 FROM se_liga_brasil.person_identity_alias a
            WHERE a.alias_person_id=p.id)
        ORDER BY p.id
    """,
        (person_id, person_id),
    ).fetchall()
