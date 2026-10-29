-- Rollback of the 1992-1994 Senate history load (service: application.senado_history).
-- Removes only rows that carry a source_record of this load (external_key prefix
-- "senate_history_1992_1994:"). People that existed before the load keep their rows; people
-- created by the load are deleted only if nothing else references them (foreign keys abort the
-- whole transaction otherwise, so later facts are never orphaned or silently deleted).
-- Run in psql with a privileged connection. It ends in ROLLBACK: read the counts first, then
-- replace the last statement by COMMIT and refresh the projection (last comment of the file).
BEGIN;
SET LOCAL lock_timeout = '10s';
SET LOCAL statement_timeout = '120s';
SELECT pg_advisory_xact_lock(hashtext('se_liga_brasil:senate_history_1992_1994'));
CREATE TEMP TABLE load_records ON COMMIT DROP AS
SELECT r.id FROM se_liga_brasil.source_record r
JOIN se_liga_brasil.source s ON s.id = r.source_id AND s.code = 'senado'
WHERE r.external_key LIKE 'senate_history_1992_1994:%';
CREATE TEMP TABLE deleted_counts(table_name text, deleted integer) ON COMMIT DROP;

WITH gone AS (DELETE FROM se_liga_brasil.political_party_affiliation
  WHERE source_record_id IN (SELECT id FROM load_records) RETURNING 1)
INSERT INTO deleted_counts SELECT 'political_party_affiliation', count(*) FROM gone;
WITH gone AS (DELETE FROM se_liga_brasil.person_fact
  WHERE source_record_id IN (SELECT id FROM load_records) RETURNING 1)
INSERT INTO deleted_counts SELECT 'person_fact', count(*) FROM gone;
WITH gone AS (DELETE FROM se_liga_brasil.office_exercise
  WHERE source_record_id IN (SELECT id FROM load_records) RETURNING 1)
INSERT INTO deleted_counts SELECT 'office_exercise', count(*) FROM gone;
WITH gone AS (DELETE FROM se_liga_brasil.office_term
  WHERE source_record_id IN (SELECT id FROM load_records) RETURNING 1)
INSERT INTO deleted_counts SELECT 'office_term', count(*) FROM gone;
WITH gone AS (DELETE FROM se_liga_brasil.person_identifier
  WHERE source_record_id IN (SELECT id FROM load_records) RETURNING 1)
INSERT INTO deleted_counts SELECT 'person_identifier', count(*) FROM gone;
WITH gone AS (DELETE FROM se_liga_brasil.person
  WHERE primary_record_id IN (SELECT id FROM load_records) RETURNING 1)
INSERT INTO deleted_counts SELECT 'person', count(*) FROM gone;
WITH gone AS (DELETE FROM se_liga_brasil.political_party
  WHERE source_record_id IN (SELECT id FROM load_records) AND code LIKE 'senado:party:%'
  RETURNING 1)
INSERT INTO deleted_counts SELECT 'political_party', count(*) FROM gone;
WITH gone AS (DELETE FROM se_liga_brasil.source_record
  WHERE id IN (SELECT id FROM load_records) RETURNING 1)
INSERT INTO deleted_counts SELECT 'source_record', count(*) FROM gone;
-- END OF DELETES
SELECT table_name, deleted FROM deleted_counts ORDER BY table_name;
ROLLBACK;
-- To make it final: replace ROLLBACK by COMMIT, then outside the transaction run
-- REFRESH MATERIALIZED VIEW se_liga_brasil.person_profile;
