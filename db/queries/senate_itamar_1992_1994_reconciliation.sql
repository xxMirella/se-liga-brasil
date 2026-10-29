-- Read-only reconciliation of the Itamar Franco Senate inventory (02/10/1992-01/01/1995).
-- Run each block inside a READ ONLY transaction. Parameter %(inventory_senate_ids)s is a text[]
-- with the official Senate ids of data/political-orientation/itamar-senate-inventory-1992-1994.json.
-- Window: valid_until / ends_before are exclusive; every block is a single batched query (no N+1).

-- name: identified_senators
SELECT i.external_id AS senate_person_id, p.id AS person_id, p.display_name, p.civil_name,
       i.source_record_id, r.source_url
FROM se_liga_brasil.person_identifier i
JOIN se_liga_brasil.source s ON s.id=i.source_id AND s.code='senado'
JOIN se_liga_brasil.person p ON p.id=se_liga_brasil.canonical_person_id(i.person_id)
JOIN se_liga_brasil.source_record r ON r.id=i.source_record_id
WHERE i.namespace='senator' AND i.external_id=ANY(%(inventory_senate_ids)s)
ORDER BY i.external_id::int;

-- name: senate_identifier_coverage
SELECT count(*) AS senate_identifiers,
       count(*) FILTER (WHERE i.external_id=ANY(%(inventory_senate_ids)s)) AS in_inventory
FROM se_liga_brasil.person_identifier i
JOIN se_liga_brasil.source s ON s.id=i.source_id AND s.code='senado'
WHERE i.namespace='senator';

-- name: senator_terms_and_exercises_in_window
SELECT i.external_id AS senate_person_id, t.represented_uf, t.legislature_key, t.official_term_key,
       t.term_start, t.term_end, e.capacity, e.starts_on, e.ends_before,
       coalesce(e.source_record_id,t.source_record_id) AS source_record_id
FROM se_liga_brasil.person_identifier i
JOIN se_liga_brasil.source s ON s.id=i.source_id AND s.code='senado'
JOIN se_liga_brasil.office_term t ON t.person_id=se_liga_brasil.canonical_person_id(i.person_id) AND t.office_kind='senator'
LEFT JOIN se_liga_brasil.office_exercise e ON e.term_id=t.id
WHERE i.namespace='senator' AND i.external_id=ANY(%(inventory_senate_ids)s)
  AND coalesce(e.ends_before,t.term_end,'infinity'::date)>'1992-10-02'
  AND coalesce(e.starts_on,t.term_start,'-infinity'::date)<'1995-01-01'
ORDER BY i.external_id::int, e.starts_on;

-- name: affiliations_overlapping_window
SELECT i.external_id AS senate_person_id, a.information_scope, a.election_context_year,
       pp.code AS political_party_code, pp.abbreviation, a.valid_from, a.valid_until,
       a.observed_on, a.evidence_kind, a.source_record_id, r.source_url
FROM se_liga_brasil.person_identifier i
JOIN se_liga_brasil.source s ON s.id=i.source_id AND s.code='senado'
JOIN se_liga_brasil.political_party_affiliation a ON a.person_id=se_liga_brasil.canonical_person_id(i.person_id)
JOIN se_liga_brasil.political_party pp ON pp.id=a.political_party_id
JOIN se_liga_brasil.source_record r ON r.id=a.source_record_id
WHERE i.namespace='senator' AND i.external_id=ANY(%(inventory_senate_ids)s)
  AND coalesce(a.valid_until,'infinity'::date)>'1992-10-02'
  AND coalesce(a.valid_from,'-infinity'::date)<'1995-01-01'
ORDER BY i.external_id::int, a.valid_from;

-- name: political_party_catalog
SELECT id AS political_party_id, code, abbreviation, name FROM se_liga_brasil.political_party ORDER BY abbreviation;

-- name: tse_1990_1994_declarations
SELECT 'electoral_candidacy' AS table_name, election_year, count(*) AS rows
FROM se_liga_brasil.electoral_candidacy WHERE election_year IN (1990,1994) GROUP BY election_year
UNION ALL
SELECT 'candidate_asset_declaration', election_year, count(*)
FROM se_liga_brasil.candidate_asset_declaration WHERE election_year IN (1990,1994) GROUP BY election_year
UNION ALL
SELECT 'political_party_affiliation_electoral', election_context_year, count(*)
FROM se_liga_brasil.political_party_affiliation WHERE election_context_year IN (1990,1994) GROUP BY election_context_year;

-- name: earliest_database_dates
SELECT (SELECT min(starts_on) FROM se_liga_brasil.office_exercise) AS earliest_exercise,
       (SELECT min(term_start) FROM se_liga_brasil.office_term WHERE office_kind='senator') AS earliest_senator_term,
       (SELECT min(held_on) FROM se_liga_brasil.voting) AS earliest_voting,
       (SELECT min(election_year) FROM se_liga_brasil.electoral_candidacy) AS earliest_candidacy_year,
       (SELECT min(valid_from) FROM se_liga_brasil.political_party_affiliation) AS earliest_affiliation_start;

-- name: senate_affiliation_scopes_overview
SELECT information_scope, count(*) AS rows, min(valid_from) AS min_valid_from, max(valid_from) AS max_valid_from
FROM se_liga_brasil.political_party_affiliation WHERE starts_with(information_scope,'institution:senado')
GROUP BY information_scope;
