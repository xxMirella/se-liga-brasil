INSERT INTO se_liga_brasil.person_fact(person_id,field_name,original_value,normalized_value,
 evidence_kind,review_status,source_record_id)
SELECT (normalized_data->>'personId')::uuid,'current_public_office_observation',normalized_data,
 normalized_data||jsonb_build_object('observedOn',left(normalized_data->>'observedAt',10),
 'institutionCode','alesp'),'administrative','verified',source_record_id FROM ingestion_batch
WHERE jsonb_typeof(normalized_data->'inExercise')='boolean'
ON CONFLICT DO NOTHING;
INSERT INTO se_liga_brasil.person_fact(person_id,field_name,original_value,normalized_value,
 evidence_kind,review_status,source_record_id)
SELECT (normalized_data->>'personId')::uuid,'alesp_institutional_profile',normalized_data,
 normalized_data,'administrative','verified',source_record_id FROM ingestion_batch
ON CONFLICT DO NOTHING;
INSERT INTO se_liga_brasil.political_party_affiliation(person_id,political_party_id,observed_on,
 source_record_id,information_valid_from,information_scope,evidence_kind)
SELECT (b.normalized_data->>'personId')::uuid,p.id,(b.normalized_data->>'observedAt')::date,
 b.source_record_id,(b.normalized_data->>'observedAt')::timestamptz,'institution:alesp','administrative'
FROM ingestion_batch b JOIN se_liga_brasil.political_party p
 ON p.code=b.normalized_data->>'politicalPartyCode'
ON CONFLICT DO NOTHING;
WITH periods AS (
 SELECT id,lead(information_valid_from) OVER(PARTITION BY person_id,information_scope
 ORDER BY information_valid_from,id) AS next_observation
 FROM se_liga_brasil.political_party_affiliation WHERE information_scope='institution:alesp'
 AND person_id IN(SELECT (normalized_data->>'personId')::uuid FROM ingestion_batch)
)
UPDATE se_liga_brasil.political_party_affiliation a SET information_valid_until=p.next_observation
FROM periods p WHERE a.id=p.id AND a.information_valid_until IS DISTINCT FROM p.next_observation;
INSERT INTO se_liga_brasil.office_term(person_id,institution_id,office_kind,represented_uf,
 legislature_key,official_term_key,term_start,term_end,source_record_id)
SELECT (b.normalized_data->>'personId')::uuid,i.id,'state_deputy','SP',m->>'legislatureKey',
 (b.normalized_data->>'personId')||':'||(m->>'legislatureKey'),
 (m->>'termStart')::date,(m->>'termEndExclusive')::date,b.source_record_id
FROM ingestion_batch b JOIN se_liga_brasil.institution i ON i.code='alesp'
CROSS JOIN LATERAL jsonb_array_elements(b.normalized_data->'mandates') m
ON CONFLICT(institution_id,official_term_key) DO NOTHING;
