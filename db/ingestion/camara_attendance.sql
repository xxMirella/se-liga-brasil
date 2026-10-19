DELETE FROM ingestion_batch WHERE classification IN ('conflicting','stale');
INSERT INTO se_liga_brasil.person_fact(person_id,field_name,original_value,normalized_value,
 evidence_kind,review_status,source_record_id)
SELECT (normalized_data->>'personId')::uuid,'camara_attendance:'||external_key,
 normalized_data,normalized_data,'administrative','verified',source_record_id
FROM ingestion_batch ON CONFLICT DO NOTHING;
