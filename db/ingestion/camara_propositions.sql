INSERT INTO se_liga_brasil.proposition(institution_id,official_key,kind,number,year,title,summary,
 introduced_on,current_status,status_as_of,source_record_id)
SELECT DISTINCT ON(i.id,b.normalized_data->>'officialKey')
 i.id,b.normalized_data->>'officialKey',b.normalized_data->>'kind',b.normalized_data->>'number',
 (b.normalized_data->>'year')::int,b.normalized_data->>'title',b.normalized_data->>'summary',
 (b.normalized_data->>'introducedOn')::date,'unknown',b.source_generated_at,b.source_record_id
FROM ingestion_batch b JOIN se_liga_brasil.institution i ON i.code='camara'
ORDER BY i.id,b.normalized_data->>'officialKey',b.source_generated_at DESC,b.source_record_id DESC
ON CONFLICT(institution_id,official_key) DO UPDATE SET summary=excluded.summary,
 source_record_id=excluded.source_record_id,status_as_of=excluded.status_as_of
WHERE excluded.status_as_of>proposition.status_as_of;
INSERT INTO se_liga_brasil.proposition_person(proposition_id,person_id,role,source_record_id)
SELECT p.id,(b.normalized_data->>'personId')::uuid,'author',b.source_record_id
FROM ingestion_batch b JOIN se_liga_brasil.institution i ON i.code='camara'
JOIN se_liga_brasil.proposition p ON p.institution_id=i.id AND p.official_key=b.normalized_data->>'officialKey'
WHERE NOT EXISTS(SELECT 1 FROM se_liga_brasil.proposition_person verified
 WHERE verified.proposition_id=p.id AND verified.person_id=(b.normalized_data->>'personId')::uuid
 AND verified.role='coauthor')
ON CONFLICT(proposition_id,person_id,role) DO NOTHING;
