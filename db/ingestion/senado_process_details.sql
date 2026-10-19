DELETE FROM ingestion_batch WHERE classification IN ('conflicting','stale');
UPDATE se_liga_brasil.proposition proposition SET
 summary=b.normalized_data->>'summary',source_record_id=b.source_record_id
FROM ingestion_batch b,se_liga_brasil.institution institution
WHERE b.kind='senado_process_summary' AND institution.code='senado'
 AND proposition.institution_id=institution.id
 AND proposition.official_key=b.normalized_data->>'official_url'
 AND nullif(b.normalized_data->>'summary','') IS NOT NULL;
