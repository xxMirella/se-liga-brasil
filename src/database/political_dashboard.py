"""Read institutional observations in one bounded, read-only database snapshot."""

from database.public_profile import PublicProfileRepository

MAX_SOURCE_OBSERVATIONS = 200_000

OBSERVATION_QUERY = """
SELECT DISTINCT ON (f.person_id, f.normalized_value->>'institutionCode',
                    least(nullif(f.normalized_value->>'observedOn','')::date,
 (s.fetched_at AT TIME ZONE 'America/Belem')::date))
 f.person_id::text AS person_id, p.display_name,
 f.source_record_id::text AS source_record_id, f.id::text AS person_fact_id,
 f.normalized_value || jsonb_build_object('politicalPartyAbbreviation',
  coalesce(f.normalized_value->>'politicalPartyAbbreviation', pp.abbreviation),
  'officeKind',coalesce(f.normalized_value->>'officeKind',
    CASE WHEN origin.code='camara' THEN 'federal_deputy' END)) AS observation,
 least(nullif(f.normalized_value->>'observedOn','')::date,
 (s.fetched_at AT TIME ZONE 'America/Belem')::date) AS observed_on,
 f.normalized_value->>'institutionCode' AS institution_code
FROM se_liga_brasil.person_fact f
JOIN se_liga_brasil.source_record s ON s.id=f.source_record_id
JOIN se_liga_brasil.person p ON p.id=f.person_id
JOIN se_liga_brasil.source origin ON origin.id=s.source_id
LEFT JOIN se_liga_brasil.political_party pp
 ON pp.code=f.normalized_value->>'politicalPartyCode'
WHERE (f.field_name='current_public_office_observation'
 OR (origin.code='camara' AND f.field_name LIKE 'camara_profile:%%'))
 AND f.review_status='verified'
 AND (%s::text[] IS NULL OR f.normalized_value->>'institutionCode'=ANY(%s))
 AND least(nullif(f.normalized_value->>'observedOn','')::date,
 (s.fetched_at AT TIME ZONE 'America/Belem')::date) BETWEEN %s AND %s
 AND NOT EXISTS(SELECT 1 FROM se_liga_brasil.person_identity_alias a
                WHERE a.alias_person_id=f.person_id)
ORDER BY f.person_id, f.normalized_value->>'institutionCode',
 least(nullif(f.normalized_value->>'observedOn','')::date,
 (s.fetched_at AT TIME ZONE 'America/Belem')::date), s.fetched_at DESC, f.id DESC
LIMIT 200001
"""


class PoliticalDashboardRepository(PublicProfileRepository):
    def fetch_observations(self, institutions, start_on, end_on):
        with self.read_snapshot():
            rows = self.connection.execute(
                OBSERVATION_QUERY, (institutions, institutions, start_on, end_on)
            ).fetchall()
        if len(rows) > MAX_SOURCE_OBSERVATIONS:
            raise ValueError("ANNUAL_SOURCE_OBSERVATION_BUDGET_EXCEEDED")
        return rows
