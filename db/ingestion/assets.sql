INSERT INTO se_liga_brasil.candidate_asset_declaration AS current(entity_id,person_id,election_year,candidate_sequence,asset_order,asset_type,description,declared_value,source_record_id,source_generated_at,value_quality_status)
SELECT b.entity_id,identity.person_id,(b.normalized_data->>'electionYear')::int,
 b.normalized_data->>'candidateSequence',b.normalized_data->>'assetOrder',b.normalized_data->>'assetType',
 b.normalized_data->>'description',(b.normalized_data->>'declaredValue')::numeric,
 b.source_record_id,b.source_generated_at,CASE WHEN (b.normalized_data->>'declaredValue')::numeric<0 THEN 'negative_requires_review' ELSE 'reported' END FROM ingestion_batch b
JOIN resolved_batch_identity identity ON identity.entity_id=b.entity_id
ON CONFLICT(entity_id) DO UPDATE SET asset_type=excluded.asset_type,description=excluded.description,
 declared_value=excluded.declared_value,value_quality_status=excluded.value_quality_status,source_record_id=excluded.source_record_id,
 source_generated_at=excluded.source_generated_at,ingested_at=now()
WHERE excluded.source_generated_at>current.source_generated_at;
