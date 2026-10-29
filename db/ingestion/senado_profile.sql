INSERT INTO se_liga_brasil.political_party_affiliation(person_id,political_party_id,observed_on,
 source_record_id,information_valid_from,information_scope,evidence_kind)
SELECT (b.normalized_data->>'personId')::uuid,p.id,b.source_generated_at::date,
 b.source_record_id,b.source_generated_at,'institution:senado','administrative'
FROM ingestion_batch b JOIN (
 SELECT abbreviation,min(id) AS id,NULL::date AS observed_from
 FROM se_liga_brasil.political_party
 GROUP BY abbreviation HAVING count(*)=1
 UNION ALL
 -- TSE 0600672-47.2023.6.00.0000, 05/03/2024: Podemos changes 19 to 20.
 -- Preserve the earlier party ID for electoral and historical observations.
 SELECT abbreviation,id,DATE '2024-03-05' FROM se_liga_brasil.political_party
 WHERE abbreviation='PODE' AND code='20'
 AND (SELECT count(*) FROM se_liga_brasil.political_party WHERE abbreviation='PODE')>1
) p ON p.abbreviation=b.normalized_data->>'politicalPartyAbbreviation'
 AND (p.observed_from IS NULL OR b.source_generated_at::date>=p.observed_from)
WHERE NOT EXISTS(
 SELECT 1 FROM se_liga_brasil.political_party_affiliation existing
 WHERE existing.person_id=(b.normalized_data->>'personId')::uuid
   AND existing.information_scope='institution:senado'
   AND existing.information_valid_from=b.source_generated_at
   AND existing.political_party_id=p.id
)
ON CONFLICT DO NOTHING;
WITH periods AS (
 SELECT id,lead(information_valid_from) OVER(PARTITION BY person_id,information_scope
 ORDER BY information_valid_from,id) AS next_observation
 FROM se_liga_brasil.political_party_affiliation WHERE information_scope='institution:senado'
)
UPDATE se_liga_brasil.political_party_affiliation a SET information_valid_until=p.next_observation
FROM periods p WHERE a.id=p.id AND a.information_valid_until IS DISTINCT FROM p.next_observation;
INSERT INTO se_liga_brasil.office_term(person_id,institution_id,office_kind,represented_uf,
 legislature_key,official_term_key,term_start,term_end,source_record_id)
SELECT (b.normalized_data->>'personId')::uuid,i.id,'senator',b.normalized_data->>'representedUf',
 b.normalized_data->>'legislatureKey',(b.normalized_data->>'personId')||':'||(b.normalized_data->>'legislatureKey'),
 (b.normalized_data->>'termStart')::date,(b.normalized_data->>'termEndExclusive')::date,b.source_record_id
FROM ingestion_batch b JOIN se_liga_brasil.institution i ON i.code='senado'
ON CONFLICT(institution_id,official_term_key) DO NOTHING;
INSERT INTO se_liga_brasil.office_exercise(term_id,starts_on,ends_before,capacity,source_record_id)
SELECT t.id,(b.normalized_data->>'exerciseStartsOn')::date,
 (b.normalized_data->>'exerciseEndExclusive')::date,b.normalized_data->>'capacity',b.source_record_id
FROM ingestion_batch b JOIN se_liga_brasil.office_term t
 ON t.person_id=(b.normalized_data->>'personId')::uuid
 AND t.legislature_key=b.normalized_data->>'legislatureKey'
JOIN se_liga_brasil.institution i ON i.id=t.institution_id AND i.code='senado'
WHERE b.normalized_data->>'inExercise'='true' AND b.normalized_data->>'exerciseStartsOn' IS NOT NULL
ON CONFLICT(term_id,starts_on) DO UPDATE SET
 ends_before=coalesce(excluded.ends_before,office_exercise.ends_before),
 capacity=excluded.capacity,source_record_id=excluded.source_record_id
WHERE (SELECT fetched_at FROM se_liga_brasil.source_record WHERE id=excluded.source_record_id)
 >(SELECT fetched_at FROM se_liga_brasil.source_record WHERE id=office_exercise.source_record_id);
INSERT INTO se_liga_brasil.person_fact(person_id,field_name,original_value,normalized_value,
 evidence_kind,review_status,source_record_id)
SELECT (normalized_data->>'personId')::uuid,'current_public_office_observation',normalized_data,
 normalized_data,'administrative','verified',source_record_id FROM ingestion_batch
ON CONFLICT DO NOTHING;

UPDATE se_liga_brasil.person p SET photo_url=b.normalized_data->>'photoUrl'
FROM ingestion_batch b
WHERE p.id=(b.normalized_data->>'personId')::uuid
 AND p.photo_url IS NULL AND b.normalized_data->>'photoUrl' IS NOT NULL;
