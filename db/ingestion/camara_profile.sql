INSERT INTO se_liga_brasil.political_party_affiliation(person_id,political_party_id,observed_on,
 source_record_id,information_valid_from,information_scope,evidence_kind)
SELECT (b.normalized_data->>'personId')::uuid,p.id,b.source_generated_at::date,
 b.source_record_id,b.source_generated_at,'institution:camara','administrative'
FROM ingestion_batch b JOIN se_liga_brasil.political_party p
 ON p.abbreviation=b.normalized_data->>'politicalPartyAbbreviation'
ON CONFLICT DO NOTHING;
WITH periods AS (
 SELECT id,lead(information_valid_from) OVER(PARTITION BY person_id,information_scope
 ORDER BY information_valid_from,id) AS next_observation
 FROM se_liga_brasil.political_party_affiliation WHERE information_scope='institution:camara'
)
UPDATE se_liga_brasil.political_party_affiliation a SET information_valid_until=p.next_observation
FROM periods p WHERE a.id=p.id AND a.information_valid_until IS DISTINCT FROM p.next_observation;
INSERT INTO se_liga_brasil.office_term(person_id,institution_id,office_kind,represented_uf,
 legislature_key,official_term_key,term_start,term_end,source_record_id)
SELECT (b.normalized_data->>'personId')::uuid,i.id,'federal_deputy',b.normalized_data->>'representedUf',
 b.normalized_data->>'legislatureKey',(b.normalized_data->>'personId')||':'||(b.normalized_data->>'legislatureKey'),
 (b.normalized_data->>'termStart')::date,(b.normalized_data->>'termEndExclusive')::date,b.source_record_id
FROM ingestion_batch b JOIN se_liga_brasil.institution i ON i.code='camara'
ON CONFLICT(institution_id,official_term_key) DO NOTHING;
INSERT INTO se_liga_brasil.office_exercise(term_id,starts_on,capacity,source_record_id)
SELECT t.id,(b.normalized_data->>'exerciseStartsOn')::date,b.normalized_data->>'capacity',b.source_record_id
FROM ingestion_batch b JOIN se_liga_brasil.office_term t
 ON t.person_id=(b.normalized_data->>'personId')::uuid
 AND t.legislature_key=b.normalized_data->>'legislatureKey'
JOIN se_liga_brasil.institution i ON i.id=t.institution_id AND i.code='camara'
WHERE b.normalized_data->>'inExercise'='true' AND b.normalized_data->>'exerciseStartsOn' IS NOT NULL
ON CONFLICT(term_id,starts_on) DO NOTHING;
UPDATE se_liga_brasil.person p SET photo_url=b.normalized_data->>'photoUrl'
FROM ingestion_batch b WHERE p.id=(b.normalized_data->>'personId')::uuid AND p.photo_url IS NULL;

-- Close only on the latest explicit institutional transition, never on file absence.
UPDATE se_liga_brasil.office_exercise e SET
 ends_before=state.starts_on::date,source_record_id=b.source_record_id
FROM ingestion_batch b JOIN se_liga_brasil.office_term t
 ON t.person_id=(b.normalized_data->>'personId')::uuid
JOIN se_liga_brasil.institution i ON i.id=t.institution_id AND i.code='camara'
JOIN LATERAL (
 SELECT event->>'dataHora' AS starts_on,event->>'situacao' AS situation
 FROM jsonb_array_elements(b.normalized_data->'history') event
 ORDER BY event->>'dataHora' DESC LIMIT 1
) state ON state.situation<>'Exercício'
WHERE e.term_id=t.id AND e.ends_before IS NULL AND b.normalized_data->>'inExercise'='false'
 AND state.starts_on::date>e.starts_on;
UPDATE se_liga_brasil.person p SET
 birth_date=coalesce(p.birth_date,(b.normalized_data->>'birthDate')::date),
 education_level=coalesce(p.education_level,b.normalized_data->>'educationLevel')
FROM ingestion_batch b WHERE p.id=(b.normalized_data->>'personId')::uuid;
