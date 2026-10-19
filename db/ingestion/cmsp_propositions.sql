DELETE FROM ingestion_batch WHERE classification IN ('conflicting','stale');
INSERT INTO se_liga_brasil.institution(code,name,level,uf,official_url)
VALUES('cmsp','Câmara Municipal de São Paulo','municipal','SP','https://www.saopaulo.sp.leg.br')
ON CONFLICT(code) DO NOTHING;
INSERT INTO se_liga_brasil.proposition(institution_id,official_key,kind,number,year,title,summary,
 introduced_on,current_status,status_as_of,source_record_id)
SELECT DISTINCT ON(i.id,b.normalized_data->>'officialKey')
 i.id,b.normalized_data->>'officialKey',b.normalized_data->>'kind',b.normalized_data->>'number',
 (b.normalized_data->>'year')::int,b.normalized_data->>'title',b.normalized_data->>'summary',
 (b.normalized_data->>'introducedOn')::date,'unknown',b.source_generated_at,b.source_record_id
FROM ingestion_batch b JOIN se_liga_brasil.institution i ON i.code='cmsp'
ORDER BY i.id,b.normalized_data->>'officialKey',b.source_generated_at DESC,b.source_record_id DESC
ON CONFLICT(institution_id,official_key) DO UPDATE SET
 summary=coalesce(excluded.summary,proposition.summary),
 introduced_on=coalesce(excluded.introduced_on,proposition.introduced_on),
 source_record_id=excluded.source_record_id,status_as_of=excluded.status_as_of
WHERE excluded.status_as_of>proposition.status_as_of
AND EXISTS(SELECT 1 FROM ingestion_batch b WHERE b.kind='cmsp_projects'
 AND b.source_record_id=excluded.source_record_id);
INSERT INTO se_liga_brasil.proposition_person(proposition_id,person_id,role,source_record_id)
SELECT DISTINCT ON(p.id,(author->>'personId')::uuid)
 p.id,(author->>'personId')::uuid,'author',b.source_record_id
FROM ingestion_batch b
JOIN se_liga_brasil.institution i ON i.code='cmsp'
JOIN se_liga_brasil.proposition p
 ON p.institution_id=i.id AND p.official_key=b.normalized_data->>'officialKey'
CROSS JOIN LATERAL jsonb_array_elements(b.normalized_data->'verifiedAuthors') author
WHERE author->>'identityMethod'='reviewed_personal_identity_evidence'
ORDER BY p.id,(author->>'personId')::uuid,b.source_generated_at DESC,b.source_record_id DESC
ON CONFLICT(proposition_id,person_id,role) DO NOTHING;
