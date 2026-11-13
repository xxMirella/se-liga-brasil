-- Rollback of 0024_drop_unused_indexes.sql: recreates the five indexes exactly as defined in
-- production pg_indexes (2026-11-12). Idempotent.
-- PENDING: not applied. Also run it before db/repairs/senate_history_1992_1994_rollback.sql.
-- Plain CREATE INDEX blocks writes to each table while it builds (about 10 s each at this size);
-- run outside a collection run, or run each statement separately with CREATE INDEX CONCURRENTLY
-- (outside any transaction) when writers must stay online.
BEGIN;
SET LOCAL lock_timeout = '10s';
CREATE INDEX IF NOT EXISTS ingestion_artifact_entity_entity_id_idx ON se_liga_brasil.ingestion_artifact_entity USING btree (entity_id);
CREATE INDEX IF NOT EXISTS person_activity_context_feed_idx ON se_liga_brasil.person_activity_context USING btree (person_id, observed_at DESC);
CREATE INDEX IF NOT EXISTS ingestion_artifact_entity_source_record_id_idx ON se_liga_brasil.ingestion_artifact_entity USING btree (source_record_id);
CREATE INDEX IF NOT EXISTS ingestion_entity_version_source_record_id_idx ON se_liga_brasil.ingestion_entity_version USING btree (source_record_id);
CREATE INDEX IF NOT EXISTS proposition_source_record_id_idx ON se_liga_brasil.proposition USING btree (source_record_id);
COMMIT;
