INSERT INTO se_liga_brasil.candidate_document AS current(entity_id,person_id,election_year,candidate_sequence,document_kind,original_entry_name,storage_reference,content_sha256,source_record_id,source_generated_at)
SELECT b.entity_id,identity.person_id,(b.normalized_data->>'electionYear')::int,
 b.normalized_data->>'candidateSequence',b.normalized_data->>'documentKind',
 b.normalized_data->>'originalEntryName',b.normalized_data->>'storageReference',
 b.normalized_data->>'documentSha256',b.source_record_id,b.source_generated_at FROM ingestion_batch b
JOIN resolved_batch_identity identity ON identity.entity_id=b.entity_id
ON CONFLICT(entity_id) DO UPDATE SET storage_reference=excluded.storage_reference,
 content_sha256=excluded.content_sha256,source_record_id=excluded.source_record_id,
 source_generated_at=excluded.source_generated_at,ingested_at=now()
WHERE excluded.source_generated_at>current.source_generated_at;
