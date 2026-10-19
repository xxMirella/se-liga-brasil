INSERT INTO se_liga_brasil.political_party_affiliation(person_id,political_party_id,observed_on,
 source_record_id,information_valid_from,information_scope,evidence_kind)
SELECT (b.normalized_data->>'personId')::uuid,p.id,b.source_generated_at::date,
 b.source_record_id,b.source_generated_at,'institution:alerj','administrative'
FROM ingestion_batch b JOIN se_liga_brasil.political_party p
 ON upper(p.abbreviation)=upper(b.normalized_data->>'politicalPartyAbbreviation')
ON CONFLICT DO NOTHING;
WITH periods AS (
 SELECT id,lead(information_valid_from) OVER(PARTITION BY person_id,information_scope
 ORDER BY information_valid_from,id) AS next_observation
 FROM se_liga_brasil.political_party_affiliation WHERE information_scope='institution:alerj'
)
UPDATE se_liga_brasil.political_party_affiliation a SET information_valid_until=p.next_observation
FROM periods p WHERE a.id=p.id AND a.information_valid_until IS DISTINCT FROM p.next_observation;
UPDATE se_liga_brasil.person p SET birth_date=coalesce(p.birth_date,
 (b.normalized_data->>'birthDate')::date)
FROM ingestion_batch b WHERE p.id=(b.normalized_data->>'personId')::uuid;
INSERT INTO se_liga_brasil.person_fact(person_id,field_name,original_value,normalized_value,
 evidence_kind,review_status,source_record_id)
SELECT (normalized_data->>'personId')::uuid,'current_public_office_observation',normalized_data,
 normalized_data,'administrative','verified',source_record_id FROM ingestion_batch
WHERE normalized_data->>'inExercise'='true'
ON CONFLICT DO NOTHING;
