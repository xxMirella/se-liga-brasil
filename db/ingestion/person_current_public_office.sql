WITH requested_people AS (
 SELECT p.id FROM se_liga_brasil.person p WHERE %(records)s::jsonb IS NULL
  OR p.id IN (SELECT (item->'normalizedData'->>'personId')::uuid
              FROM jsonb_array_elements(%(records)s::jsonb) item)
), latest_observation AS (
 SELECT DISTINCT ON(f.person_id,i.id) f.person_id,i.id AS institution_id,
  f.normalized_value->>'officeKind' AS office_kind,
  f.normalized_value->>'inExercise' AS in_exercise,
  f.normalized_value->>'exerciseEndExclusive' AS exercise_ends_before,
  f.normalized_value->>'exerciseStartsOn' AS exercise_starts_on,
  f.normalized_value->>'observedOn' AS observed_on,r.fetched_at,f.source_record_id
 FROM se_liga_brasil.person_fact f
 JOIN requested_people requested ON requested.id=f.person_id
 JOIN se_liga_brasil.source_record r ON r.id=f.source_record_id
 JOIN se_liga_brasil.institution i ON i.code=f.normalized_value->>'institutionCode'
 WHERE f.field_name='current_public_office_observation'
  AND f.evidence_kind='administrative' AND f.review_status='verified'
  AND f.normalized_value->>'observedOn'>=(current_date-30)::text
  AND f.normalized_value->>'observedOn'<=current_date::text
 ORDER BY f.person_id,i.id,f.normalized_value->>'observedOn' DESC,r.fetched_at DESC,f.id DESC
), current_exercise AS (
 SELECT t.person_id,t.institution_id,t.office_kind,t.id AS term_id,
  r.fetched_at,e.source_record_id
 FROM se_liga_brasil.office_term t
 JOIN requested_people requested ON requested.id=t.person_id
 JOIN se_liga_brasil.office_exercise e ON e.term_id=t.id
 JOIN se_liga_brasil.source_record r ON r.id=e.source_record_id
 LEFT JOIN latest_observation o ON o.person_id=t.person_id AND o.institution_id=t.institution_id
 WHERE e.starts_on<=current_date AND (e.ends_before IS NULL OR e.ends_before>current_date)
  AND (t.term_start IS NULL OR t.term_start<=current_date)
  AND (t.term_end IS NULL OR t.term_end>current_date)
  AND r.fetched_at>=now()-interval '30 days'
  AND NOT(coalesce(o.in_exercise,'true')='false'
          AND o.observed_on>=r.fetched_at::date::text)
), observed_exercise AS (
 SELECT o.person_id,o.institution_id,o.office_kind,t.id AS term_id,
  o.fetched_at,o.source_record_id
 FROM latest_observation o
 LEFT JOIN LATERAL (
  SELECT id FROM se_liga_brasil.office_term
  WHERE person_id=o.person_id AND institution_id=o.institution_id
   AND (term_start IS NULL OR term_start<=current_date)
   AND (term_end IS NULL OR term_end>current_date)
  ORDER BY term_start DESC NULLS LAST,id DESC LIMIT 1
 ) t ON true
 WHERE o.in_exercise='true' AND o.office_kind IS NOT NULL
  AND (o.exercise_ends_before IS NULL OR o.exercise_ends_before>current_date::text)
  AND (o.exercise_starts_on IS NULL OR o.exercise_starts_on<=current_date::text)
), confirmed_office AS (
 SELECT DISTINCT ON(person_id) * FROM (
  SELECT * FROM current_exercise UNION ALL SELECT * FROM observed_exercise
 ) candidates ORDER BY person_id,fetched_at DESC,source_record_id DESC
), confirmed_absence AS (
 SELECT DISTINCT ON(f.person_id) f.person_id,f.source_record_id
 FROM se_liga_brasil.person_fact f JOIN requested_people requested ON requested.id=f.person_id
 JOIN se_liga_brasil.source_record r ON r.id=f.source_record_id
 WHERE f.field_name='public_office_status' AND f.evidence_kind='administrative'
  AND f.review_status='verified' AND f.normalized_value->>'hasCurrentPublicOffice'='false'
  AND f.normalized_value->>'scope'='all_public_offices'
  AND f.normalized_value->>'validFrom'<=current_date::text
  AND f.normalized_value->>'validUntil'>current_date::text
  AND r.fetched_at>=now()-interval '30 days'
 ORDER BY f.person_id,r.fetched_at DESC,f.id DESC
), resolved AS (
 SELECT p.id,CASE WHEN o.person_id IS NOT NULL AND a.person_id IS NULL THEN true
  WHEN a.person_id IS NOT NULL AND o.person_id IS NULL THEN false END AS has_office,
  CASE WHEN a.person_id IS NULL THEN o.office_kind END AS office_kind,
  CASE WHEN a.person_id IS NULL THEN o.institution_id END AS institution_id,
  CASE WHEN a.person_id IS NULL THEN o.term_id END AS term_id,
  CASE WHEN o.person_id IS NOT NULL AND a.person_id IS NULL THEN o.source_record_id
   WHEN a.person_id IS NOT NULL AND o.person_id IS NULL THEN a.source_record_id END AS source_record_id
 FROM se_liga_brasil.person p JOIN requested_people requested ON requested.id=p.id
 LEFT JOIN confirmed_office o ON o.person_id=p.id
 LEFT JOIN confirmed_absence a ON a.person_id=p.id
)
UPDATE se_liga_brasil.person p SET has_current_public_office=r.has_office,
 current_public_office_kind=r.office_kind,current_public_office_institution_id=r.institution_id,
 current_public_office_term_id=r.term_id,public_office_status_as_of=current_date,
 public_office_status_source_record_id=r.source_record_id,updated_at=now()
FROM resolved r WHERE p.id=r.id AND
 (p.has_current_public_office,p.current_public_office_kind,p.current_public_office_institution_id,
  p.current_public_office_term_id,p.public_office_status_source_record_id,p.public_office_status_as_of)
 IS DISTINCT FROM
 (r.has_office,r.office_kind,r.institution_id,r.term_id,r.source_record_id,current_date);
