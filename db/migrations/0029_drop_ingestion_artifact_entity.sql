-- PENDING: not applied. Not wired to db-migrate or operations.py.
-- Storage (R5): drop ingestion_artifact_entity (~44 MB, ~304k rows, INSERT-only in reconcile.sql, never read).
-- It records which artifact (downloaded file) observed which entity. About 85% of entities appear in a
-- single artifact (derivable from source_record.storage_reference / ingestion_artifact.storage_reference);
-- ~15% reappear in later artifacts and ONLY this table records the re-observation. That information is
-- therefore archived outside the database (artifact resource_id + content_sha256, entity_kind,
-- external_key, entity content_sha256) BEFORE the drop. From now on the history of observations lives in
-- that archive plus ingestion_artifact (one row per downloaded file) and source_record (one row per
-- distinct content); idempotency by hash is unaffected (it uses source_record/ingestion_entity hashes).
-- Idempotent (DROP TABLE IF EXISTS). Space returns at once; no VACUUM FULL needed.
-- Operator step, in the same session, after the archive is written and its row count checked:
--   SET se_liga.archive_0029_confirmed = 'yes';
-- DEPLOY ORDER: ship the reconcile.sql that no longer writes the table first; old code fails after the drop.
-- Rollback: db/rollbacks/0029_recreate_ingestion_artifact_entity.sql (structure only; data from the archive).
BEGIN;
SET LOCAL lock_timeout = '10s';
DO $$ DECLARE archived_rows bigint; BEGIN
 IF to_regclass('se_liga_brasil.ingestion_artifact_entity') IS NOT NULL THEN
  SELECT count(*) INTO archived_rows FROM se_liga_brasil.ingestion_artifact_entity;
  IF archived_rows > 0 AND coalesce(current_setting('se_liga.archive_0029_confirmed', true), '') <> 'yes' THEN
   RAISE EXCEPTION 'Archive % ingestion_artifact_entity rows, then SET se_liga.archive_0029_confirmed = ''yes''', archived_rows;
  END IF;
 END IF;
END $$;
DROP TABLE IF EXISTS se_liga_brasil.ingestion_artifact_entity;
COMMIT;
