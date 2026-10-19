INSERT INTO se_liga_brasil.political_party AS current(code,name,abbreviation,source_record_id,
 last_election_context_year,last_observed_at)
SELECT DISTINCT ON (b.normalized_data->>'politicalPartyCode')
 b.normalized_data->>'politicalPartyCode',b.normalized_data->>'politicalPartyName',
 b.normalized_data->>'politicalPartyAbbreviation',b.source_record_id,
 (b.normalized_data->>'electionYear')::int,b.source_generated_at
FROM ingestion_batch b JOIN resolved_batch_identity identity ON identity.entity_id=b.entity_id
ORDER BY b.normalized_data->>'politicalPartyCode',(b.normalized_data->>'electionYear')::int DESC,
 b.source_generated_at DESC,b.source_record_id DESC
ON CONFLICT(code) DO UPDATE SET name=excluded.name,abbreviation=excluded.abbreviation,
 source_record_id=excluded.source_record_id,last_election_context_year=excluded.last_election_context_year,
 last_observed_at=excluded.last_observed_at
WHERE (excluded.last_election_context_year,excluded.last_observed_at)>
 (coalesce(current.last_election_context_year,0),coalesce(current.last_observed_at,'-infinity'));
INSERT INTO se_liga_brasil.political_party_affiliation(person_id,political_party_id,observed_on,
 source_record_id,information_valid_from,information_scope,election_context_year,evidence_kind)
SELECT identity.person_id,political_party.id,b.source_generated_at::date,b.source_record_id,
 b.source_generated_at,'electoral:'||(b.normalized_data->>'electionYear'),
 (b.normalized_data->>'electionYear')::int,'electoral_declaration'
FROM ingestion_batch b JOIN resolved_batch_identity identity ON identity.entity_id=b.entity_id
JOIN se_liga_brasil.political_party political_party ON political_party.code=b.normalized_data->>'politicalPartyCode'
ON CONFLICT(person_id,political_party_id,source_record_id) DO NOTHING;
WITH touched AS (
 SELECT DISTINCT identity.person_id,'electoral:'||(b.normalized_data->>'electionYear') AS scope
 FROM ingestion_batch b JOIN resolved_batch_identity identity ON identity.entity_id=b.entity_id
), instants AS (
 SELECT DISTINCT affiliation.person_id,affiliation.information_scope,
 affiliation.information_valid_from FROM se_liga_brasil.political_party_affiliation affiliation
 JOIN touched ON touched.person_id=affiliation.person_id AND touched.scope=affiliation.information_scope
), periods AS (
 SELECT person_id,information_scope,information_valid_from,
 lead(information_valid_from) OVER(PARTITION BY person_id,information_scope
 ORDER BY information_valid_from) AS next_observation FROM instants
)
UPDATE se_liga_brasil.political_party_affiliation affiliation
SET information_valid_until=periods.next_observation FROM periods
WHERE affiliation.person_id=periods.person_id
 AND affiliation.information_scope=periods.information_scope
 AND affiliation.information_valid_from=periods.information_valid_from;
UPDATE se_liga_brasil.electoral_candidacy candidacy SET political_party_id=political_party.id,
 political_party_affiliation_id=affiliation.id
FROM ingestion_batch b JOIN resolved_batch_identity identity ON identity.entity_id=b.entity_id
JOIN se_liga_brasil.political_party political_party ON political_party.code=b.normalized_data->>'politicalPartyCode'
JOIN se_liga_brasil.political_party_affiliation affiliation ON affiliation.person_id=identity.person_id
 AND affiliation.political_party_id=political_party.id AND affiliation.source_record_id=b.source_record_id
WHERE candidacy.source_id=%(source_id)s AND candidacy.person_id=identity.person_id
 AND candidacy.election_year=(b.normalized_data->>'electionYear')::int
 AND candidacy.candidate_sequence=b.normalized_data->>'candidateSequence'
 AND candidacy.source_record_id=b.source_record_id;
