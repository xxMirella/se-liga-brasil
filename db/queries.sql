-- Examples for a backend using PostgreSQL bind parameters. Never interpolate IDs.

-- 1. Profile card. Compute age on read, so it does not become stale in the snapshot.
SELECT *, extract(year FROM age(current_date, birth_date))::int AS age_today
FROM se_liga_brasil.person_profile WHERE person_id=$1::uuid;

-- 2. Name search + UF, stable cursor. NULL cursor for first page.
SELECT person_id, slug, display_name, current_offices, last_observed_political_party, data_coverage, refreshed_at
FROM se_liga_brasil.person_profile
WHERE search_document @@ plainto_tsquery('portuguese',$1)
 AND represented_ufs @> ARRAY[$2]::text[]
 AND ($3::uuid IS NULL OR person_id>$3::uuid)
ORDER BY person_id LIMIT 25;

-- 3. Authored works, deduplicated when a source assigns author and coauthor roles.
SELECT p.id, p.kind, p.number, p.year, p.title, p.current_status, p.source_record_id
FROM se_liga_brasil.proposition p
WHERE p.id>coalesce($2::bigint,0)
 AND EXISTS(SELECT 1 FROM se_liga_brasil.proposition_person pp
 WHERE pp.proposition_id=p.id AND pp.person_id=$1::uuid AND pp.role IN ('author','coauthor'))
ORDER BY p.id LIMIT 25;

-- 4. Individual votes: choice and collective outcome are separate columns.
SELECT v.id, v.held_at, v.subject, pv.choice, v.result, p.title, pv.source_record_id
FROM se_liga_brasil.person_vote pv
JOIN se_liga_brasil.voting v ON v.id=pv.voting_id
JOIN se_liga_brasil.proposition p ON p.id=v.proposition_id
WHERE pv.person_id=$1::uuid AND v.id>coalesce($2::bigint,0)
ORDER BY v.id LIMIT 25;

-- 5. Amendment roles, then latest snapshot per source-normalized execution slice.
WITH page AS (
 SELECT DISTINCT amendment_id FROM se_liga_brasil.amendment_person
 WHERE person_id=$1::uuid AND amendment_id>coalesce($2::bigint,0)
 ORDER BY amendment_id LIMIT 25
)
SELECT a.id, a.budget_year, a.amendment_type, a.description, s.*
FROM page JOIN se_liga_brasil.budget_amendment a ON a.id=page.amendment_id
LEFT JOIN LATERAL (
 SELECT DISTINCT ON (slice_key) slice_key, as_of, beneficiary_name,
 execution_year, committed, liquidated, paid, source_record_id
 FROM se_liga_brasil.amendment_execution_snapshot WHERE amendment_id=a.id
 ORDER BY slice_key, as_of DESC
) s ON true ORDER BY a.id,s.slice_key;

-- 6. Effective days by office: union overlaps; excludes future days.
-- Inclusive start, exclusive end; current date included through current_date + 1.
WITH ranges AS (
 SELECT t.office_kind, range_agg(daterange(e.starts_on,
 least(coalesce(e.ends_before,current_date+1),current_date+1),'[)')) AS periods
 FROM se_liga_brasil.office_term t JOIN se_liga_brasil.office_exercise e ON e.term_id=t.id
 WHERE t.person_id=$1::uuid AND e.starts_on<=current_date GROUP BY t.office_kind
)
SELECT office_kind, sum(upper(r)-lower(r)) AS effective_days
FROM ranges CROSS JOIN LATERAL unnest(periods) r GROUP BY office_kind;
