-- Rollback of 0028_null_unread_source_record_payload.sql: restore step is done by the CLI, this
-- file is the completion gate. PENDING: not applied.
--
-- 1. Restore from the verified archive (writes only into rows whose payload is NULL today):
--      python scripts/archive_ingestion_data.py restore --archive-dir data/database_snapshot/<UTC> \
--        --table 'se_liga_brasil.source_record@payload_without_readers.ndjson.gz' \
--        --mode fill-null-columns --column payload --dry-run     # first: counts only, rolled back
--      (repeat without --dry-run; it commits per batch of 1000 rows and can be re-run)
--    If a whole row is missing (not only its payload) run the same command with --mode insert.
-- 2. Run this file: it fails while any row of the archived types still has payload NULL.
--    Restored payloads equal the originals (verify checked content_sha256 = hash_content(payload)).
-- 3. Before the next reconcile run, nothing else is needed: reconcile.sql writes payload again.
DO $$
DECLARE pending bigint;
BEGIN
  SELECT count(*) INTO pending
  FROM se_liga_brasil.source_record r JOIN se_liga_brasil.source s ON s.id = r.source_id
  WHERE r.payload IS NULL
    AND ((s.code = 'alesp' AND split_part(r.external_key, ':', 1) IN ('alesp_attendance', 'alesp_propositions'))
      OR (s.code = 'tse' AND split_part(r.external_key, ':', 1) IN ('asset', 'complement')));
  IF pending > 0 THEN
    RAISE EXCEPTION 'PAYLOAD_RESTORE_INCOMPLETE: % rows still have payload NULL', pending;
  END IF;
  RAISE NOTICE 'All archived-type source_record rows have payload.';
END $$;
