-- A parser correction is a separately traceable derived exercise fact.
INSERT INTO se_liga_brasil.office_exercise(term_id,starts_on,capacity,source_record_id)
SELECT t.id,(b.normalized_data->>'exerciseStartsOn')::date,
 b.normalized_data->>'capacity',b.source_record_id
FROM ingestion_batch b JOIN se_liga_brasil.office_term t
 ON t.person_id=(b.normalized_data->>'personId')::uuid
 AND t.legislature_key=b.normalized_data->>'legislatureKey'
JOIN se_liga_brasil.institution i ON i.id=t.institution_id AND i.code='camara'
WHERE b.normalized_data->>'inExercise'='true'
 AND b.normalized_data->>'exerciseStartsOn' IS NOT NULL
ON CONFLICT(term_id,starts_on) DO UPDATE SET source_record_id=excluded.source_record_id
WHERE (SELECT fetched_at FROM se_liga_brasil.source_record
       WHERE id=se_liga_brasil.office_exercise.source_record_id)
 <=(SELECT fetched_at FROM se_liga_brasil.source_record WHERE id=excluded.source_record_id);
