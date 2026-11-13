-- Rollback of 0029_drop_ingestion_artifact_entity.sql. Idempotent.
-- Recreates the empty table as it was in production after 0024 (primary key only; the two secondary
-- indexes were dropped by 0024). Reload the rows from the archive written before 0029
-- (artifact resource_id + content_sha256 -> artifact_id; entity_kind + external_key -> entity_id).
BEGIN;
SET LOCAL lock_timeout = '10s';
CREATE TABLE IF NOT EXISTS se_liga_brasil.ingestion_artifact_entity (
 artifact_id bigint NOT NULL REFERENCES se_liga_brasil.ingestion_artifact,
 entity_id bigint NOT NULL REFERENCES se_liga_brasil.ingestion_entity,
 source_record_id bigint NOT NULL REFERENCES se_liga_brasil.source_record,
 PRIMARY KEY(artifact_id,entity_id)
);
ALTER TABLE se_liga_brasil.ingestion_artifact_entity ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE se_liga_brasil.ingestion_artifact_entity FROM PUBLIC;
COMMIT;
