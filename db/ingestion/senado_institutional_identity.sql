-- Provider codes identify source subjects, never canonical people by themselves.
UPDATE ingestion_batch b SET normalized_data=jsonb_set(b.normalized_data,'{personId}',
 to_jsonb(r.person_id::text)) FROM personal_resolution r WHERE b.entity_id=r.entity_id;
INSERT INTO se_liga_brasil.person_identifier(source_id,namespace,external_id,
 person_id,source_record_id)
SELECT %(source_id)s,'senator',normalized_data->>'officialSenatorCode',person_id,
 source_record_id FROM personal_resolution
ON CONFLICT(source_id,namespace,external_id) DO UPDATE
 SET source_record_id=excluded.source_record_id
 WHERE se_liga_brasil.person_identifier.person_id=excluded.person_id;
