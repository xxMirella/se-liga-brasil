DELETE FROM ingestion_batch WHERE classification IN ('conflicting','stale');
CREATE TEMP TABLE resolved_batch_identity ON COMMIT DROP AS
SELECT b.entity_id,(array_agg(DISTINCT i.person_id))[1] AS person_id FROM ingestion_batch b
JOIN se_liga_brasil.electoral_candidacy i ON i.source_id=%(source_id)s
 AND i.election_year=(b.normalized_data->>'electionYear')::int
 AND i.candidate_sequence=b.normalized_data->>'candidateSequence'
GROUP BY b.entity_id HAVING count(DISTINCT i.person_id)=1;
INSERT INTO se_liga_brasil.ingestion_rejection(run_id,artifact_id,resource_id,entry_name,row_number,reason_code,payload_sha256,details)
SELECT %(run_id)s,%(artifact_id)s,%(resource_id)s,b.entry_name,b.row_number,
 'CANDIDATE_IDENTITY_NOT_FOUND',b.content_sha256,b.diagnostic_context||jsonb_build_object(
 'lookup_external_id',b.normalized_data->>'candidateSequence',
 'dependency_hint','Confira a candidatura no arquivo e linha candidate_source. Ela pode ter sido rejeitada antes.') FROM ingestion_batch b
WHERE NOT EXISTS(SELECT 1 FROM resolved_batch_identity identity WHERE identity.entity_id=b.entity_id);
DELETE FROM ingestion_batch b WHERE NOT EXISTS
 (SELECT 1 FROM resolved_batch_identity identity WHERE identity.entity_id=b.entity_id);
INSERT INTO se_liga_brasil.person_fact(person_id,field_name,original_value,normalized_value,evidence_kind,review_status,source_record_id)
SELECT identity.person_id,'tse:'||b.kind||':'||b.external_key,b.normalized_data,b.normalized_data,
 'declaration','pending',b.source_record_id FROM ingestion_batch b
JOIN resolved_batch_identity identity ON identity.entity_id=b.entity_id
ON CONFLICT(person_id,field_name,source_record_id) DO NOTHING;
