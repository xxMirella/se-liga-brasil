DELETE FROM ingestion_batch WHERE classification IN ('conflicting','stale');
INSERT INTO se_liga_brasil.person_fact(person_id,field_name,original_value,normalized_value,
 evidence_kind,review_status,source_record_id)
SELECT se_liga_brasil.canonical_person_id((normalized_data->>'personId')::uuid),
 'alerj_historical_activity:'||(normalized_data->>'eventKey'),normalized_data,normalized_data,
 'administrative','verified',source_record_id FROM ingestion_batch
WHERE normalized_data->>'identityMethod'='unique_full_name_birth_date:official_public_name_bridge'
 AND normalized_data->>'nominalBallotVerified'='false'
ON CONFLICT DO NOTHING;
