DELETE FROM ingestion_batch WHERE classification IN ('conflicting','stale');
CREATE TEMP TABLE projection_identity ON COMMIT DROP AS
SELECT DISTINCT ON (normalized_data->>'electionYear',normalized_data->>'candidateSequence')
 normalized_data->>'electionYear' AS election_year,
 normalized_data->>'candidateSequence' AS candidate_sequence,
 person_id,source_record_id,normalized_data FROM personal_resolution
ORDER BY normalized_data->>'electionYear',normalized_data->>'candidateSequence',source_record_id DESC;
INSERT INTO se_liga_brasil.electoral_candidacy AS current(source_id,external_key,person_id,election_year,election_id,candidate_sequence,election_round,represented_uf,office_code,office_name,political_party_code,political_party_name,political_party_abbreviation,candidacy_status,election_result,source_record_id,source_generated_at)
SELECT DISTINCT ON (b.normalized_data->>'electionYear',b.normalized_data->>'electionId',
 b.normalized_data->>'candidateSequence',b.normalized_data->>'electionRound')
 %(source_id)s,(b.normalized_data->>'electionYear')||':'||(b.normalized_data->>'electionId')||':'||(b.normalized_data->>'candidateSequence')||':'||(b.normalized_data->>'electionRound'),
 i.person_id,(b.normalized_data->>'electionYear')::int,b.normalized_data->>'electionId',
 b.normalized_data->>'candidateSequence',(b.normalized_data->>'electionRound')::int,
 b.normalized_data->>'representedUf',b.normalized_data->>'officeCode',b.normalized_data->>'officeName',
 b.normalized_data->>'politicalPartyCode',b.normalized_data->>'politicalPartyName',
 b.normalized_data->>'politicalPartyAbbreviation',b.normalized_data->>'candidacyStatus',
 b.normalized_data->>'electionResult',b.source_record_id,b.source_generated_at
FROM ingestion_batch b JOIN projection_identity i ON i.election_year=b.normalized_data->>'electionYear'
 AND i.candidate_sequence=b.normalized_data->>'candidateSequence'
ORDER BY b.normalized_data->>'electionYear',b.normalized_data->>'electionId',
 b.normalized_data->>'candidateSequence',b.normalized_data->>'electionRound',
 b.source_generated_at DESC,b.external_key
ON CONFLICT(source_id,external_key) DO UPDATE SET
 candidacy_status=excluded.candidacy_status,election_result=excluded.election_result,
 political_party_code=excluded.political_party_code,political_party_name=excluded.political_party_name,
 political_party_abbreviation=excluded.political_party_abbreviation,
 source_record_id=excluded.source_record_id,source_generated_at=excluded.source_generated_at,ingested_at=now()
WHERE excluded.source_generated_at>current.source_generated_at AND current.person_id=excluded.person_id;
DROP TABLE projection_identity;
-- Only the TSE-owned electoral profile can be updated by this connector; older election years cannot overwrite newer profiles.
UPDATE se_liga_brasil.person person SET
 normalized_name=coalesce(b.identity_evidence->>'normalizedName',person.normalized_name),
 civil_name=b.normalized_data->>'civilName',display_name=b.normalized_data->>'displayName',
 birth_date=coalesce(person.birth_date,(b.normalized_data->>'birthDate')::date),
 education_level=coalesce(b.normalized_data->>'educationLevel',person.education_level),
 primary_record_id=b.source_record_id,updated_at=now()
FROM ingestion_batch b JOIN personal_resolution identity ON identity.entity_id=b.entity_id,
 se_liga_brasil.source_record previous
WHERE person.id=identity.person_id AND person.primary_record_id=previous.id
 AND previous.source_id=%(source_id)s AND b.kind='candidate'
 AND b.classification IN ('new','changed')
 AND (b.normalized_data->>'electionYear')::int>=coalesce((previous.payload->>'electionYear')::int,0)
 AND b.source_generated_at>=previous.effective_at;

DROP TABLE personal_resolution;
