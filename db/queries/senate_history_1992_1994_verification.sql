-- Read-only checks after the 1992-1994 Senate load. Run inside a READ ONLY transaction.

-- 1. Rows created by the load, by table (the dry-run report lists the same numbers).
WITH load_records AS (
  SELECT r.id FROM se_liga_brasil.source_record r
  JOIN se_liga_brasil.source s ON s.id = r.source_id AND s.code = 'senado'
  WHERE r.external_key LIKE 'senate_history_1992_1994:%'
)
SELECT 'source_record' AS table_name, count(*) FROM load_records
UNION ALL SELECT 'person', count(*) FROM se_liga_brasil.person
  WHERE primary_record_id IN (SELECT id FROM load_records)
UNION ALL SELECT 'person_identifier', count(*) FROM se_liga_brasil.person_identifier
  WHERE source_record_id IN (SELECT id FROM load_records)
UNION ALL SELECT 'office_term', count(*) FROM se_liga_brasil.office_term
  WHERE source_record_id IN (SELECT id FROM load_records)
UNION ALL SELECT 'office_exercise', count(*) FROM se_liga_brasil.office_exercise
  WHERE source_record_id IN (SELECT id FROM load_records)
UNION ALL SELECT 'political_party_affiliation', count(*)
  FROM se_liga_brasil.political_party_affiliation
  WHERE source_record_id IN (SELECT id FROM load_records)
UNION ALL SELECT 'political_party', count(*) FROM se_liga_brasil.political_party
  WHERE code LIKE 'senado:party:%'
UNION ALL SELECT 'person_fact', count(*) FROM se_liga_brasil.person_fact
  WHERE source_record_id IN (SELECT id FROM load_records);

-- 2. Affiliations of the window by person, in order, with the exclusive end.
SELECT pe.display_name, i.external_id AS senate_id, p.code AS political_party_code,
       p.abbreviation, a.valid_from, a.valid_until, a.information_scope
FROM se_liga_brasil.political_party_affiliation a
JOIN se_liga_brasil.person pe ON pe.id = a.person_id
JOIN se_liga_brasil.person_identifier i ON i.person_id = pe.id AND i.namespace = 'senator'
JOIN se_liga_brasil.political_party p ON p.id = a.political_party_id
WHERE a.information_scope = 'institution:senado:historical_affiliations'
ORDER BY pe.display_name, a.valid_from;

-- 3. No Senate ID shared by two people and no overlapping affiliation of one person.
SELECT external_id, count(DISTINCT person_id) AS people
FROM se_liga_brasil.person_identifier WHERE namespace = 'senator'
GROUP BY external_id HAVING count(DISTINCT person_id) > 1;

SELECT a.person_id, a.id AS first_id, b.id AS second_id
FROM se_liga_brasil.political_party_affiliation a
JOIN se_liga_brasil.political_party_affiliation b
  ON b.person_id = a.person_id AND b.id > a.id
 AND b.information_scope = a.information_scope
 AND a.information_scope = 'institution:senado:historical_affiliations'
 AND a.valid_from < coalesce(b.valid_until, 'infinity') AND b.valid_from < coalesce(a.valid_until, 'infinity');
