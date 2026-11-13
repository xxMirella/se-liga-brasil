-- R4: set source_record.payload to NULL for the record types no code reads (about 105 MB).
-- PENDING: not applied. Destructive for the database copy; the data survives in the local archive.
--
-- Types (source.code : prefix of external_key) - keep in sync with
-- src/service/archive_export/source_record_types.py (tests compare both):
--   alesp:alesp_attendance, alesp:alesp_propositions, tse:asset, tse:complement
-- NOT included on purpose: tse candidate/history (read through electoral_candidacy.source_record_id),
-- Camara kinds (public_propositions.py reads documentUrl), payroll kinds, senado/alerj kinds.
--
-- PRECONDITIONS (docs/arquivamento-ingestao.md):
--   1. python scripts/archive_ingestion_data.py export --scope snapshot   (full snapshot in data/)
--   2. python scripts/archive_ingestion_data.py verify --archive-dir <dir>   (exit 0; it prints
--      "VERIFIED manifest_sha256=<hash>" and writes verification.json)
--   3. In the SAME session that runs this file, acknowledge the verified archive:
--        SET se_liga_brasil.verified_archive_manifest_sha256 = '<hash printed by verify>';
--      Without it this file changes NOTHING and only emits a WARNING (so schema-building tools that
--      replay every migration cannot null data by accident). Check the output for the NOTICE below.
--
-- Only rows with storage_reference IS NOT NULL are changed, so the CHECK
-- (payload IS NOT NULL OR storage_reference IS NOT NULL) always holds.
-- The file has no BEGIN/COMMIT: each batch of 20000 ids commits by itself (DO block with COMMIT),
-- so run it in autocommit (psql -f), never inside a transaction block. It is idempotent and can be
-- re-run (also periodically: reconcile.sql still writes payload for new records of these types).
-- Space returns to the table only after VACUUM FULL / pg_repack (scripts/maintenance_reclaim_table_bloat.py).
-- Rollback: db/rollbacks/0028_restore_source_record_payload.sql (restores from the archive).
SET lock_timeout = '10s';
SET statement_timeout = 0;
DO $$
DECLARE
  acknowledged text := current_setting('se_liga_brasil.verified_archive_manifest_sha256', true);
  batch_size constant integer := 20000;
  last_id bigint := 0;
  upper_id bigint;
  batch_rows bigint;
  total_rows bigint := 0;
BEGIN
  IF acknowledged IS NULL OR acknowledged !~ '^[a-f0-9]{64}$' THEN
    RAISE WARNING 'SKIPPED, nothing changed: ARCHIVE_NOT_ACKNOWLEDGED (export + verify, then SET se_liga_brasil.verified_archive_manifest_sha256)';
    RETURN;
  END IF;
  RAISE NOTICE 'Acknowledged archive manifest sha256 %', acknowledged;
  LOOP
    SELECT max(id) INTO upper_id FROM (
      SELECT id FROM se_liga_brasil.source_record WHERE id > last_id ORDER BY id LIMIT batch_size) window_ids;
    EXIT WHEN upper_id IS NULL;
    UPDATE se_liga_brasil.source_record r SET payload = NULL
    FROM se_liga_brasil.source s
    WHERE r.id > last_id AND r.id <= upper_id AND s.id = r.source_id
      AND r.payload IS NOT NULL AND r.storage_reference IS NOT NULL
      AND ((s.code = 'alesp' AND split_part(r.external_key, ':', 1) IN ('alesp_attendance', 'alesp_propositions'))
        OR (s.code = 'tse' AND split_part(r.external_key, ':', 1) IN ('asset', 'complement')));
    GET DIAGNOSTICS batch_rows = ROW_COUNT;
    total_rows := total_rows + batch_rows;
    last_id := upper_id;
    COMMIT;
  END LOOP;
  RAISE NOTICE 'source_record.payload set to NULL on % rows', total_rows;
END $$;
