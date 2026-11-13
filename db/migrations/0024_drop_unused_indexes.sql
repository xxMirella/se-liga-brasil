-- Storage: drop five secondary indexes that no query reads. Idempotent; no table or data change.
-- APPLIED in production on 2026-11-12 (1347 MB -> 1315 MB). Not wired to db-migrate or operations.py.
-- Revalidated read-only on production 2026-11-12 (idx_scan since creation; stats never reset):
--   ingestion_artifact_entity_entity_id_idx         8.1 MB  0 scans  FK to ingestion_entity (never deleted)
--   person_activity_context_feed_idx                2.7 MB  0 scans  no reader in src/ or db/
--   ingestion_artifact_entity_source_record_id_idx  8.3 MB  0 scans  FK to source_record
--   ingestion_entity_version_source_record_id_idx   7.6 MB  0 scans  FK to source_record
--   proposition_source_record_id_idx                4.7 MB  0 scans  FK to source_record
-- Deliberately kept: ingestion_entity_source_record_id_idx (still being scanned).
-- CONDITION for the three source_record FK indexes: deleting a source_record row now scans those
-- tables once per deleted row. Before running db/repairs/senate_history_1992_1994_rollback.sql
-- (346 records, 120 s statement_timeout) or any source_record DELETE, apply
-- db/rollbacks/0024_recreate_unused_indexes.sql first. The pipeline itself never deletes them.
-- Space returns to the database at once (DROP INDEX), no VACUUM FULL needed.
-- Plain DROP INDEX (not CONCURRENTLY) because the file runs inside a transaction; it takes a
-- short ACCESS EXCLUSIVE lock per table, so run it outside a collection run.
BEGIN;
SET LOCAL lock_timeout = '10s';
DROP INDEX IF EXISTS se_liga_brasil.ingestion_artifact_entity_entity_id_idx;
DROP INDEX IF EXISTS se_liga_brasil.person_activity_context_feed_idx;
DROP INDEX IF EXISTS se_liga_brasil.ingestion_artifact_entity_source_record_id_idx;
DROP INDEX IF EXISTS se_liga_brasil.ingestion_entity_version_source_record_id_idx;
DROP INDEX IF EXISTS se_liga_brasil.proposition_source_record_id_idx;
COMMIT;
