-- Preserve facts produced before the corrected SPL identity bridge for audit.
UPDATE se_liga_brasil.person_fact
SET review_status='conflicting'
WHERE field_name LIKE 'alesp_attendance:%%'
 AND review_status='verified'
 AND normalized_value->>'identityMethod' IS DISTINCT FROM 'official_profile_to_roster_IdSPL';
DELETE FROM ingestion_batch WHERE classification IN ('conflicting','stale');
INSERT INTO se_liga_brasil.person_fact(person_id,field_name,original_value,normalized_value,
 evidence_kind,review_status,source_record_id)
SELECT (normalized_data->>'personId')::uuid,'alesp_attendance:'||external_key,
 normalized_data,normalized_data,'administrative','verified',source_record_id
FROM ingestion_batch ON CONFLICT DO NOTHING;
