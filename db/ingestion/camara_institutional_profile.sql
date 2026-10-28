-- Only an unambiguous canonical abbreviation is reconciled; the source spelling remains in facts.
INSERT INTO se_liga_brasil.political_party_affiliation(person_id,political_party_id,observed_on,
 source_record_id,information_valid_from,information_scope,evidence_kind)
SELECT (b.normalized_data->>'personId')::uuid,p.id,b.source_generated_at::date,
 b.source_record_id,b.source_generated_at,'institution:camara','administrative'
FROM ingestion_batch b JOIN (
 SELECT abbreviation,min(id) AS id FROM se_liga_brasil.political_party
 GROUP BY abbreviation HAVING count(*)=1
) p ON p.abbreviation=b.normalized_data->>'politicalPartyAbbreviation'
WHERE NOT EXISTS(SELECT 1 FROM se_liga_brasil.political_party_affiliation a
 WHERE a.person_id=(b.normalized_data->>'personId')::uuid AND a.political_party_id=p.id
 AND a.information_scope='institution:camara' AND a.information_valid_from=b.source_generated_at)
ON CONFLICT DO NOTHING;
INSERT INTO se_liga_brasil.person_fact(person_id,field_name,original_value,normalized_value,
 evidence_kind,review_status,source_record_id)
SELECT (normalized_data->>'personId')::uuid,'current_public_office_observation',normalized_data,
 normalized_data,'administrative','verified',source_record_id FROM ingestion_batch
ON CONFLICT DO NOTHING;
UPDATE se_liga_brasil.person p SET photo_url=coalesce(p.photo_url,b.normalized_data->>'photoUrl'),
 education_level=coalesce(p.education_level,b.normalized_data->>'educationLevel')
FROM ingestion_batch b WHERE p.id=(b.normalized_data->>'personId')::uuid;
