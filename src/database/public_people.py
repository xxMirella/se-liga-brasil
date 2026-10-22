"""Read-only canonical public person fields; private identity stays in the adapter."""

from database.public_profile import PublicProfileRepository


class PublicPeopleRepository(PublicProfileRepository):
    def search_people(self, query, as_of, cursor):
        name, identifier = cursor or (None, None)
        pattern = "%" + query.q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        return self.connection.execute(
            """SELECT p.id::text AS person_id,p.display_name,p.slug
            FROM se_liga_brasil.person p
            WHERE NOT EXISTS(SELECT 1 FROM se_liga_brasil.person_identity_alias a
                WHERE a.alias_person_id=p.id)
              AND p.display_name ILIKE %s
              AND (%s::text IS NULL OR (p.display_name,p.id)>(%s,%s::uuid))
              AND ((%s::text IS NULL AND %s::text IS NULL) OR EXISTS(
                SELECT 1 FROM se_liga_brasil.office_term t
                JOIN se_liga_brasil.office_exercise e ON e.term_id=t.id
                WHERE t.person_id=p.id AND e.starts_on<=%s
                AND (e.ends_before IS NULL OR e.ends_before>%s)
                AND (%s::text IS NULL OR t.represented_uf=%s)
                AND (%s::text IS NULL OR t.office_kind=%s)))
              AND (%s::text IS NULL OR EXISTS(
                SELECT 1 FROM se_liga_brasil.political_party_affiliation a
                JOIN se_liga_brasil.political_party pp ON pp.id=a.political_party_id
                WHERE a.person_id=p.id AND a.evidence_kind<>'electoral_declaration'
                AND a.observed_on<=%s AND (a.valid_from IS NULL OR a.valid_from<=%s)
                AND (a.valid_until IS NULL OR a.valid_until>%s)
                AND (a.information_valid_until IS NULL OR a.information_valid_until::date>%s)
                AND a.observed_on=(SELECT max(latest.observed_on)
                  FROM se_liga_brasil.political_party_affiliation latest
                  WHERE latest.person_id=p.id AND latest.observed_on<=%s
                  AND latest.evidence_kind<>'electoral_declaration'
                  AND (latest.valid_until IS NULL OR latest.valid_until>%s)
                  AND (latest.information_valid_until IS NULL
                    OR latest.information_valid_until::date>%s))
                AND lower(pp.abbreviation)=lower(%s)))
            ORDER BY p.display_name,p.id LIMIT %s""",
            (
                pattern,
                name,
                name,
                identifier,
                query.uf,
                query.office_kind,
                as_of,
                as_of,
                query.uf,
                query.uf,
                query.office_kind,
                query.office_kind,
                query.political_party,
                as_of,
                as_of,
                as_of,
                as_of,
                as_of,
                as_of,
                as_of,
                query.political_party,
                query.limit + 1,
            ),
        ).fetchall()

    def fetch_public_person(self, person_id):
        return self.connection.execute(
            """SELECT p.id::text AS person_id,p.display_name,p.slug,p.birth_date,p.photo_url,
              p.education_level,p.has_current_public_office,p.public_office_status_as_of,
              p.current_public_office_kind,i.code AS snapshot_institution_code,
              i.name AS snapshot_institution_name
            FROM se_liga_brasil.person p
            LEFT JOIN se_liga_brasil.institution i ON i.id=p.current_public_office_institution_id
            WHERE p.id=%s::uuid AND NOT EXISTS(SELECT 1 FROM se_liga_brasil.person_identity_alias a
              WHERE a.alias_person_id=p.id)""",
            (person_id,),
        ).fetchone()

    def fetch_current_exercises(self, person_id, as_of):
        return self.connection.execute(
            """SELECT DISTINCT ON (t.id) e.id AS exercise_id,t.id AS term_id,
              t.office_kind,t.represented_uf,
              i.code AS institution_code,i.name AS institution_name,
              e.starts_on,e.ends_before,e.capacity
            FROM se_liga_brasil.office_term t
            JOIN se_liga_brasil.office_exercise e ON e.term_id=t.id
            JOIN se_liga_brasil.institution i ON i.id=t.institution_id
            JOIN se_liga_brasil.source_record exercise_source
              ON exercise_source.id=e.source_record_id
            WHERE t.person_id=%s::uuid AND e.starts_on<=%s
              AND (e.ends_before IS NULL OR e.ends_before>%s)
              AND (t.term_start IS NULL OR t.term_start<=%s)
              AND (t.term_end IS NULL OR t.term_end>%s)
              AND NOT EXISTS(
                SELECT 1 FROM se_liga_brasil.person_fact f
                JOIN se_liga_brasil.source_record observation_source
                  ON observation_source.id=f.source_record_id
                WHERE f.person_id=t.person_id AND f.field_name='current_public_office_observation'
                  AND f.review_status='verified' AND f.evidence_kind='administrative'
                  AND f.normalized_value->>'institutionCode'=i.code
                  AND f.normalized_value->>'observedOn'<=%s::text
                  AND f.normalized_value->>'observedOn'>=e.starts_on::text
                  AND f.normalized_value->>'inExercise'='false'
                  AND observation_source.fetched_at>=exercise_source.fetched_at
              )
            ORDER BY t.id,exercise_source.fetched_at DESC,e.starts_on,e.id DESC LIMIT 101""",
            (person_id, as_of, as_of, as_of, as_of, as_of),
        ).fetchall()

    def fetch_public_affiliations(self, person_id, as_of):
        return self.connection.execute(
            """SELECT pp.abbreviation,pp.name,a.observed_on,a.evidence_kind,
              a.valid_from,a.valid_until,a.information_scope
            FROM se_liga_brasil.political_party_affiliation a
            JOIN se_liga_brasil.political_party pp ON pp.id=a.political_party_id
            WHERE a.person_id=%s::uuid AND a.observed_on<=%s
              AND (a.valid_from IS NULL OR a.valid_from<=%s)
              AND (a.valid_until IS NULL OR a.valid_until>%s)
              AND (a.information_valid_until IS NULL OR a.information_valid_until::date>%s)
            ORDER BY (a.evidence_kind<>'electoral_declaration') DESC,
              a.observed_on DESC,a.id DESC LIMIT 101""",
            (person_id, as_of, as_of, as_of, as_of),
        ).fetchall()

    def fetch_latest_public_payments(self, person_id, as_of):
        return self.connection.execute(
            """SELECT DISTINCT ON (organization_code,office_kind,payroll_kind)
              organization_code,office_kind,payroll_kind,competence,currency,
              gross_amount,tax_amount,net_amount
            FROM se_liga_brasil.person_payroll_payment
            WHERE person_id=%s::uuid AND identity_status='verified' AND competence<=%s
            ORDER BY organization_code,office_kind,payroll_kind,
              competence DESC,observed_at DESC,id DESC
            LIMIT 101""",
            (person_id, as_of.replace(day=1)),
        ).fetchall()
