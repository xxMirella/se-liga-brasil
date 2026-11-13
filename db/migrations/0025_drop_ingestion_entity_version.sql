-- PENDING: not applied. Not wired to db-migrate or operations.py.
-- Storage (R1): replace the table ingestion_entity_version (~210 MB, 276k rows, no reader in src/, db/
-- or scripts/) by a read-only compatibility view computed from source_record + ingestion_entity.
-- Why a view and not just removing references: tests and ad hoc audits count versions
-- ("how many distinct contents did this entity have"), and the view answers that with the same column
-- names (entity_id, content_sha256, normalized_data, source_record_id, first_ingested_at).
-- Where history lives afterwards: reconcile.sql already writes one source_record per
-- (source_id, 'kind:external_key', content_sha256); that row IS the version (measured on production
-- sample: 100% of versions have a matching source_record with identical payload). Nothing is lost
-- except the version's own first_ingested_at, which the view approximates by source_record.fetched_at
-- (differs by more than one day in ~58% of rows). The exact first_ingested_at of the ~151 entities
-- with more than one version must be archived BEFORE this runs (see guard below).
-- Idempotent: if ingestion_entity_version is already a view, only CREATE OR REPLACE VIEW runs.
-- Space: DROP TABLE returns the files to the operating system at once; no VACUUM FULL needed.
-- Run outside a collection run (short ACCESS EXCLUSIVE lock, 10 s lock_timeout).
-- Operator step, in the same session, after the archive file is written and checked:
--   SET se_liga.archive_0025_confirmed = 'yes';
-- DEPLOY ORDER: ship the reconcile.sql that no longer writes the table first; old code fails after the drop.
-- Rollback: db/rollbacks/0025_recreate_ingestion_entity_version.sql
BEGIN;
SET LOCAL lock_timeout = '10s';
SET LOCAL statement_timeout = '300s';
DO $$
DECLARE
 unmatched bigint;
 multi_version_entities bigint;
BEGIN
 IF (SELECT c.relkind FROM pg_class c WHERE c.oid = to_regclass('se_liga_brasil.ingestion_entity_version')) = 'r' THEN
  SELECT count(*) INTO unmatched
  FROM se_liga_brasil.ingestion_entity_version v
  JOIN se_liga_brasil.ingestion_entity e ON e.id = v.entity_id
  WHERE NOT EXISTS (SELECT 1 FROM se_liga_brasil.source_record sr
   WHERE sr.source_id = e.source_id AND sr.external_key = e.entity_kind || ':' || e.external_key
    AND sr.content_sha256 = v.content_sha256);
  IF unmatched > 0 THEN
   RAISE EXCEPTION 'ingestion_entity_version has % rows without a matching source_record; not reconstructable', unmatched;
  END IF;
  SELECT count(*) INTO multi_version_entities FROM (
   SELECT entity_id FROM se_liga_brasil.ingestion_entity_version GROUP BY entity_id HAVING count(*) > 1) multi;
  IF multi_version_entities > 0 AND coalesce(current_setting('se_liga.archive_0025_confirmed', true), '') <> 'yes' THEN
   RAISE EXCEPTION 'Archive first_ingested_at of % multi-version entities, then SET se_liga.archive_0025_confirmed = ''yes''', multi_version_entities;
  END IF;
  DROP TABLE se_liga_brasil.ingestion_entity_version;
 END IF;
END $$;
CREATE OR REPLACE VIEW se_liga_brasil.ingestion_entity_version WITH (security_invoker = true) AS
SELECT e.id AS entity_id, sr.content_sha256, sr.payload AS normalized_data,
 sr.id AS source_record_id, sr.fetched_at AS first_ingested_at
FROM se_liga_brasil.ingestion_entity e
JOIN se_liga_brasil.source_record sr ON sr.source_id = e.source_id
 AND sr.external_key = e.entity_kind || ':' || e.external_key;
COMMENT ON VIEW se_liga_brasil.ingestion_entity_version IS
 'Compatibility view: one row per distinct content of an entity, derived from source_record. normalized_data is source_record.payload (NULL if that payload was archived); first_ingested_at is source_record.fetched_at.';
REVOKE ALL ON se_liga_brasil.ingestion_entity_version FROM PUBLIC;
DO $$ DECLARE role_name text; BEGIN
 FOREACH role_name IN ARRAY ARRAY['anon','authenticated'] LOOP
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN
   EXECUTE format('REVOKE ALL ON se_liga_brasil.ingestion_entity_version FROM %I', role_name);
  END IF;
 END LOOP;
END $$;
COMMIT;
