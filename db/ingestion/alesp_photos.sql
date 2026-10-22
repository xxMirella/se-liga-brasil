INSERT INTO se_liga_brasil.person_fact(person_id,field_name,original_value,normalized_value,
 evidence_kind,review_status,source_record_id)
SELECT (normalized_data->>'personId')::uuid,'alesp_official_photo',normalized_data,
 normalized_data,'administrative','verified',source_record_id FROM ingestion_batch
ON CONFLICT DO NOTHING;

UPDATE se_liga_brasil.person p SET photo_url=b.normalized_data->>'photoUrl'
FROM ingestion_batch b
WHERE p.id=(b.normalized_data->>'personId')::uuid
 AND p.photo_url IS NULL AND b.normalized_data->>'photoUrl' IS NOT NULL;
