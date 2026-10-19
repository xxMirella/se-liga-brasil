TRUNCATE ingestion_batch;
INSERT INTO ingestion_batch(kind,external_key,content_sha256,normalized_data,source_generated_at,entry_name,row_number,identity_evidence,diagnostic_context)
SELECT r->>'kind',r->>'externalKey',r->>'contentSha256',r->'normalizedData',
       (r->>'sourceGeneratedAt')::timestamptz,r->>'entryName',(r->>'rowNumber')::int,r->'identityEvidence',coalesce(r->'diagnosticContext','{}'::jsonb)
FROM jsonb_array_elements(%(records)s::jsonb) r;
UPDATE ingestion_batch b SET classification=CASE
 WHEN existing.id IS NULL THEN 'new'
 WHEN b.source_generated_at<existing.source_generated_at THEN 'stale'
 WHEN b.content_sha256=existing.content_sha256 THEN 'unchanged'
 WHEN b.source_generated_at=existing.source_generated_at THEN 'conflicting'
 ELSE 'changed' END
FROM (SELECT b.external_key,e.id,e.source_generated_at,e.content_sha256 FROM ingestion_batch b
 LEFT JOIN se_liga_brasil.ingestion_entity e ON e.source_id=%(source_id)s
 AND e.entity_kind=b.kind AND e.external_key=b.external_key) existing
WHERE b.external_key=existing.external_key;
INSERT INTO se_liga_brasil.source_record(source_id,external_key,source_url,content_sha256,fetched_at,effective_at,payload,storage_reference)
SELECT %(source_id)s,kind||':'||external_key,%(source_url)s,content_sha256,%(fetched_at)s,
       source_generated_at,normalized_data,%(archive_path)s FROM ingestion_batch
ON CONFLICT(source_id,external_key,content_sha256) DO NOTHING;
UPDATE ingestion_batch b SET source_record_id=r.id FROM se_liga_brasil.source_record r
WHERE r.source_id=%(source_id)s AND r.external_key=b.kind||':'||b.external_key
AND r.content_sha256=b.content_sha256;
INSERT INTO se_liga_brasil.ingestion_entity AS current(source_id,entity_kind,external_key,content_sha256,normalized_data,source_record_id,source_generated_at)
SELECT %(source_id)s,kind,external_key,content_sha256,normalized_data,source_record_id,source_generated_at
FROM ingestion_batch
ON CONFLICT(source_id,entity_kind,external_key) DO UPDATE SET
 content_sha256=excluded.content_sha256,normalized_data=excluded.normalized_data,
 source_record_id=excluded.source_record_id,source_generated_at=excluded.source_generated_at,
 last_ingested_at=CASE WHEN current.content_sha256<>excluded.content_sha256 THEN now() ELSE current.last_ingested_at END
WHERE excluded.source_generated_at>current.source_generated_at;
UPDATE ingestion_batch b SET entity_id=e.id FROM se_liga_brasil.ingestion_entity e
WHERE e.source_id=%(source_id)s AND e.entity_kind=b.kind AND e.external_key=b.external_key;
INSERT INTO se_liga_brasil.ingestion_entity_version(entity_id,content_sha256,normalized_data,source_record_id)
SELECT entity_id,content_sha256,normalized_data,source_record_id FROM ingestion_batch
ON CONFLICT(entity_id,content_sha256) DO NOTHING;
INSERT INTO se_liga_brasil.ingestion_artifact_entity(artifact_id,entity_id,source_record_id)
SELECT %(artifact_id)s,entity_id,source_record_id FROM ingestion_batch
ON CONFLICT(artifact_id,entity_id) DO NOTHING;
INSERT INTO se_liga_brasil.ingestion_rejection(run_id,artifact_id,resource_id,entry_name,row_number,reason_code,payload_sha256,details)
SELECT %(run_id)s,%(artifact_id)s,%(resource_id)s,entry_name,row_number,'SAME_TIMESTAMP_CONFLICT',content_sha256,diagnostic_context
FROM ingestion_batch WHERE classification='conflicting';
