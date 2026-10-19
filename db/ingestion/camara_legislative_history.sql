DELETE FROM ingestion_batch WHERE classification IN ('conflicting','stale');

INSERT INTO se_liga_brasil.proposition(institution_id,official_key,kind,number,year,title,
 summary,introduced_on,current_status,status_as_of,source_record_id)
SELECT i.id,b.normalized_data->>'officialKey',b.normalized_data->>'kind',
 b.normalized_data->>'number',(b.normalized_data->>'year')::int,
 b.normalized_data->>'title',b.normalized_data->>'summary',
 (b.normalized_data->>'introducedOn')::date,'unknown',b.source_generated_at,b.source_record_id
FROM ingestion_batch b JOIN se_liga_brasil.institution i ON i.code='camara'
WHERE b.kind='camara_legislative_detail'
ON CONFLICT(institution_id,official_key) DO UPDATE SET summary=excluded.summary,
 introduced_on=COALESCE(excluded.introduced_on,proposition.introduced_on),
 status_as_of=excluded.status_as_of,source_record_id=excluded.source_record_id
WHERE excluded.status_as_of>=proposition.status_as_of;

INSERT INTO se_liga_brasil.proposition_event
 (proposition_id,official_event_key,occurred_at,event_type,description,source_record_id)
SELECT p.id,b.normalized_data->>'eventKey',
 (b.normalized_data->>'occurredAt')::timestamp AT TIME ZONE 'America/Sao_Paulo',
 b.normalized_data->>'eventType',b.normalized_data->>'description',b.source_record_id
FROM ingestion_batch b JOIN se_liga_brasil.institution i ON i.code='camara'
JOIN se_liga_brasil.proposition p ON p.institution_id=i.id
 AND p.official_key=b.normalized_data->>'officialKey'
WHERE b.kind IN ('camara_legislative_tramitacoes','camara_legislative_votacoes')
ON CONFLICT(proposition_id,official_event_key) DO UPDATE
SET occurred_at=excluded.occurred_at,event_type=excluded.event_type,
 description=excluded.description,source_record_id=excluded.source_record_id;

DELETE FROM se_liga_brasil.proposition_person link
USING ingestion_batch b,se_liga_brasil.proposition p,se_liga_brasil.institution i
WHERE b.kind='camara_legislative_autores' AND b.normalized_data->>'role'='coauthor'
 AND link.role='author' AND link.person_id=(b.normalized_data->>'personId')::uuid
 AND link.proposition_id=p.id AND p.institution_id=i.id AND i.code='camara'
 AND p.official_key=b.normalized_data->>'officialKey';

INSERT INTO se_liga_brasil.proposition_person(proposition_id,person_id,role,source_record_id)
SELECT p.id,(b.normalized_data->>'personId')::uuid,b.normalized_data->>'role',b.source_record_id
FROM ingestion_batch b JOIN se_liga_brasil.institution i ON i.code='camara'
JOIN se_liga_brasil.proposition p ON p.institution_id=i.id
 AND p.official_key=b.normalized_data->>'officialKey'
WHERE b.kind='camara_legislative_autores'
ON CONFLICT(proposition_id,person_id,role) DO UPDATE
SET source_record_id=excluded.source_record_id;
