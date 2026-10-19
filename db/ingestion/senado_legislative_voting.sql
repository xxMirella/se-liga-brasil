DELETE FROM ingestion_batch WHERE classification IN ('conflicting','stale');
INSERT INTO se_liga_brasil.institution(code,name,level,uf,official_url)
VALUES('senado','Senado Federal','federal','BR','https://www.senado.leg.br')
ON CONFLICT(code) DO NOTHING;
INSERT INTO se_liga_brasil.proposition(institution_id,official_key,kind,number,year,title,
 current_status,status_as_of,source_record_id)
SELECT DISTINCT ON(b.normalized_data->>'proposition_source_key') i.id,
 'https://legis.senado.leg.br/dadosabertos/processo/'||(b.normalized_data->>'proposition_source_key'),
 b.normalized_data->>'proposition_kind',b.normalized_data->>'proposition_number',
 (b.normalized_data->>'proposition_year')::int,b.normalized_data->>'proposition_title',
 'unknown',b.source_generated_at,b.source_record_id
FROM ingestion_batch b JOIN se_liga_brasil.institution i ON i.code='senado'
WHERE b.kind='senado_voting'
ORDER BY b.normalized_data->>'proposition_source_key',b.source_generated_at DESC
ON CONFLICT(institution_id,official_key) DO NOTHING;
INSERT INTO se_liga_brasil.voting(institution_id,proposition_id,official_key,held_at,held_on,
 date_precision,subject,method,result,legislative_body_code,session_key,sequence_number,
 round_number,subject_kind,stage,nominal_availability,collective_result_code,source_record_id)
SELECT i.id,p.id,b.normalized_data->>'source_key',NULL,
 (b.normalized_data->>'occurred_on')::date,'day',b.normalized_data->>'description',
 b.normalized_data->>'method','unknown',b.normalized_data->>'legislative_body_code',
 b.normalized_data->>'session_key',(b.normalized_data->>'sequence_number')::int,
 (b.normalized_data->>'round_number')::int,b.normalized_data->>'subject_kind',
 b.normalized_data->>'stage',b.normalized_data->>'nominal_availability',
 b.normalized_data->>'collective_result_code',b.source_record_id
FROM ingestion_batch b JOIN se_liga_brasil.institution i ON i.code='senado'
JOIN se_liga_brasil.proposition p ON p.institution_id=i.id AND p.official_key=
 'https://legis.senado.leg.br/dadosabertos/processo/'||(b.normalized_data->>'proposition_source_key')
WHERE b.kind='senado_voting'
ON CONFLICT(institution_id,official_key) DO UPDATE SET held_on=excluded.held_on,
 subject=excluded.subject,method=excluded.method,legislative_body_code=excluded.legislative_body_code,
 session_key=excluded.session_key,sequence_number=excluded.sequence_number,
 round_number=excluded.round_number,nominal_availability=excluded.nominal_availability,
 collective_result_code=excluded.collective_result_code,source_record_id=excluded.source_record_id;
UPDATE se_liga_brasil.person_vote_revision revision SET valid_until=clock_timestamp()
FROM ingestion_batch b JOIN se_liga_brasil.institution i ON i.code='senado'
JOIN se_liga_brasil.voting v ON v.institution_id=i.id AND v.official_key=b.normalized_data->>'voting_key'
WHERE b.kind='senado_person_vote' AND revision.voting_id=v.id
 AND revision.person_id=(b.normalized_data->>'person_id')::uuid AND revision.valid_until IS NULL
 AND (revision.choice,revision.participation_status,revision.political_party_observed,
 revision.source_choice_code,revision.identity_method) IS DISTINCT FROM
 (b.normalized_data->>'choice',b.normalized_data->>'participation_status',
 b.normalized_data->>'political_party_observed',b.normalized_data->>'source_choice_code',
 b.normalized_data->>'identity_method');
INSERT INTO se_liga_brasil.person_vote_revision(voting_id,person_id,choice,participation_status,
 political_party_observed,source_choice_code,identity_method,source_record_id)
SELECT v.id,(b.normalized_data->>'person_id')::uuid,b.normalized_data->>'choice',
 b.normalized_data->>'participation_status',b.normalized_data->>'political_party_observed',
 b.normalized_data->>'source_choice_code',b.normalized_data->>'identity_method',b.source_record_id
FROM ingestion_batch b JOIN se_liga_brasil.institution i ON i.code='senado'
JOIN se_liga_brasil.voting v ON v.institution_id=i.id AND v.official_key=b.normalized_data->>'voting_key'
WHERE b.kind='senado_person_vote' AND NOT EXISTS(
 SELECT 1 FROM se_liga_brasil.person_vote_revision r WHERE r.voting_id=v.id
 AND r.person_id=(b.normalized_data->>'person_id')::uuid AND r.valid_until IS NULL);
INSERT INTO se_liga_brasil.person_vote(voting_id,person_id,choice,participation_status,
 political_party_observed,source_choice_code,identity_method,source_record_id)
SELECT v.id,(b.normalized_data->>'person_id')::uuid,b.normalized_data->>'choice',
 b.normalized_data->>'participation_status',b.normalized_data->>'political_party_observed',
 b.normalized_data->>'source_choice_code',b.normalized_data->>'identity_method',b.source_record_id
FROM ingestion_batch b JOIN se_liga_brasil.institution i ON i.code='senado'
JOIN se_liga_brasil.voting v ON v.institution_id=i.id AND v.official_key=b.normalized_data->>'voting_key'
WHERE b.kind='senado_person_vote'
ON CONFLICT(voting_id,person_id) DO UPDATE SET choice=excluded.choice,
 participation_status=excluded.participation_status,political_party_observed=excluded.political_party_observed,
 source_choice_code=excluded.source_choice_code,identity_method=excluded.identity_method,
 source_record_id=excluded.source_record_id;
UPDATE se_liga_brasil.person_vote_revision revision SET valid_until=clock_timestamp()
FROM ingestion_batch b JOIN se_liga_brasil.institution i ON i.code='senado'
JOIN se_liga_brasil.voting v ON v.institution_id=i.id AND v.official_key=b.normalized_data->>'source_key'
WHERE b.kind='senado_voting' AND v.method='secret'
 AND revision.voting_id=v.id AND revision.valid_until IS NULL;
DELETE FROM se_liga_brasil.person_vote vote
USING ingestion_batch b,se_liga_brasil.voting v,se_liga_brasil.institution i
WHERE b.kind='senado_voting' AND i.code='senado' AND v.institution_id=i.id
 AND v.official_key=b.normalized_data->>'source_key' AND v.method='secret' AND vote.voting_id=v.id;
