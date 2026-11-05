"""Read-only canonical public person fields; private identity stays in the adapter."""

from database.public_profile import PublicProfileRepository

# Registry variants such as "MDB (1980-)" belong to the same party as "MDB".
BASE_ABBREVIATION_SQL = r"upper(regexp_replace(pp.abbreviation, '\s*\([^)]*\)\s*$', ''))"

# Sorting keys, per mode. A person without a current party or state sorts last ("~" follows every
# letter in no collation we know, so a "0"/"1" prefix ranks them), and name then id break ties,
# so the (key, name, id) keyset is total and stable.
CURRENT_AFFILIATION_FILTER = """a.person_id=p.id AND a.evidence_kind<>'electoral_declaration'
  AND a.observed_on<=%(as_of)s AND (a.valid_from IS NULL OR a.valid_from<=%(as_of)s)
  AND (a.valid_until IS NULL OR a.valid_until>%(as_of)s)
  AND (a.information_valid_until IS NULL OR a.information_valid_until::date>%(as_of)s)"""
SORT_KEY_SQL = {
    "name": "''",
    "party": f"""COALESCE((SELECT '0'||{BASE_ABBREVIATION_SQL}
      FROM se_liga_brasil.political_party_affiliation a
      JOIN se_liga_brasil.political_party pp ON pp.id=a.political_party_id
      WHERE {CURRENT_AFFILIATION_FILTER} AND pp.abbreviation<>''
      ORDER BY a.observed_on DESC,a.id LIMIT 1),'1')""",
    "state": """COALESCE((SELECT '0'||t.represented_uf FROM se_liga_brasil.office_term t
      JOIN se_liga_brasil.office_exercise e ON e.term_id=t.id
      WHERE t.person_id=p.id AND t.represented_uf IS NOT NULL AND e.starts_on<=%(as_of)s
      AND (e.ends_before IS NULL OR e.ends_before>%(as_of)s)
      ORDER BY e.starts_on DESC LIMIT 1),'1')""",
}


class PublicPeopleRepository(PublicProfileRepository):
    def search_people(self, query, as_of, cursor):
        sort_key, name, identifier = cursor or (None, None, None)
        pattern = "%" + query.q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        return self.connection.execute(
            f"""SELECT person_id,display_name,slug,sort_key FROM (
              SELECT p.id AS id,p.id::text AS person_id,p.display_name,p.slug,
                {SORT_KEY_SQL[query.sort]} AS sort_key
              FROM se_liga_brasil.person p
              WHERE NOT EXISTS(SELECT 1 FROM se_liga_brasil.person_identity_alias a
                  WHERE a.alias_person_id=p.id)
                AND p.display_name ILIKE %(pattern)s
                AND (%(uf)s::text IS NULL AND %(office_kind)s::text IS NULL OR EXISTS(
                  SELECT 1 FROM se_liga_brasil.office_term t
                  JOIN se_liga_brasil.office_exercise e ON e.term_id=t.id
                  WHERE t.person_id=p.id AND e.starts_on<=%(as_of)s
                  AND (e.ends_before IS NULL OR e.ends_before>%(as_of)s)
                  AND (%(uf)s::text IS NULL OR t.represented_uf=%(uf)s)
                  AND (%(office_kind)s::text IS NULL OR t.office_kind=%(office_kind)s)))
                AND (%(party)s::text IS NULL OR EXISTS(
                  SELECT 1 FROM se_liga_brasil.political_party_affiliation a
                  JOIN se_liga_brasil.political_party pp ON pp.id=a.political_party_id
                  WHERE a.person_id=p.id AND a.evidence_kind<>'electoral_declaration'
                  AND a.observed_on<=%(as_of)s AND (a.valid_from IS NULL OR a.valid_from<=%(as_of)s)
                  AND (a.valid_until IS NULL OR a.valid_until>%(as_of)s)
                  AND (a.information_valid_until IS NULL
                    OR a.information_valid_until::date>%(as_of)s)
                  AND a.observed_on=(SELECT max(latest.observed_on)
                    FROM se_liga_brasil.political_party_affiliation latest
                    WHERE latest.person_id=p.id AND latest.observed_on<=%(as_of)s
                    AND latest.evidence_kind<>'electoral_declaration'
                    AND (latest.valid_until IS NULL OR latest.valid_until>%(as_of)s)
                    AND (latest.information_valid_until IS NULL
                      OR latest.information_valid_until::date>%(as_of)s))
                  AND {BASE_ABBREVIATION_SQL}=upper(%(party)s)))
            ) ranked
            WHERE %(after_name)s::text IS NULL
              OR (sort_key,display_name,id)>(%(after_key)s,%(after_name)s,%(after_id)s::uuid)
            ORDER BY sort_key,display_name,id LIMIT %(limit)s""",
            {
                "pattern": pattern, "as_of": as_of, "uf": query.uf,
                "office_kind": query.office_kind, "party": query.political_party,
                "after_key": sort_key, "after_name": name, "after_id": identifier,
                "limit": query.limit + 1,
            },
        ).fetchall()

    def list_current_political_parties(self, as_of):
        """Parties with at least one person affiliated today, one row per base abbreviation."""
        return self.connection.execute(
            f"""SELECT {BASE_ABBREVIATION_SQL} AS abbreviation,min(pp.name) AS name
            FROM se_liga_brasil.political_party pp
            WHERE pp.abbreviation<>'' AND EXISTS(
              SELECT 1 FROM se_liga_brasil.political_party_affiliation a
              WHERE a.political_party_id=pp.id AND a.evidence_kind<>'electoral_declaration'
              AND a.observed_on<=%(as_of)s AND (a.valid_from IS NULL OR a.valid_from<=%(as_of)s)
              AND (a.valid_until IS NULL OR a.valid_until>%(as_of)s)
              AND (a.information_valid_until IS NULL
                OR a.information_valid_until::date>%(as_of)s))
            GROUP BY 1 ORDER BY 1""",
            {"as_of": as_of},
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
              e.starts_on,e.ends_before,e.capacity,t.term_end
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
