DELETE FROM ingestion_batch WHERE classification IN ('conflicting','stale');
INSERT INTO se_liga_brasil.person_fact(person_id,field_name,original_value,normalized_value,
 evidence_kind,review_status,source_record_id)
SELECT (normalized_data->>'personId')::uuid,'alesp_participation:'||external_key,
 normalized_data,normalized_data,'administrative','verified',source_record_id
FROM ingestion_batch
WHERE normalized_data->>'presenceConfirmed'='true'
 AND normalized_data->>'scope'='historical_participation_observed'
 AND (normalized_data->>'date')::date <= CURRENT_DATE
ON CONFLICT DO NOTHING;
