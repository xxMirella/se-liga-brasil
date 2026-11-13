-- PENDING: not applied. Not wired to db-migrate or operations.py.
-- Storage (R2): remove ingestion_entity.normalized_data (~131 MB). It is a verbatim copy of
-- source_record.payload of the row that ingestion_entity.source_record_id points to (production
-- samples: 100% equal, all entity kinds). The current content of an entity is read through
-- source_record_id; readers changed in the same release (public_propositions.py, audit_name_only_payroll.py).
-- Safe by construction: a row is nulled ONLY when its value equals the referenced payload, and the
-- column is dropped ONLY if no non-null value remains. If source_record.payload was archived (nulled)
-- first, the guard below fails: run this migration before archiving payload, or restore it.
-- Not wrapped in BEGIN/COMMIT on purpose: statement_timeout applies per top-level statement, and the
-- UPDATEs are split into id ranges of 50,000 rows so each one is short. Run it with autocommit
-- (psql -f); each range is a tiny DO block so a re-run after DROP COLUMN is a no-op; it is idempotent and resumable (rows already NULL are skipped; re-run after any failure).
-- Space: UPDATE ... SET NULL and DROP COLUMN do NOT shrink the file; dead TOAST/heap pages are only
-- reusable. The ~131 MB returns to the operating system only after a table rewrite
-- (pg_repack, or scripts/maintenance_reclaim_table_bloat.py); no VACUUM FULL here because it holds
-- ACCESS EXCLUSIVE for the whole rewrite and needs free disk equal to the table size.
-- DEPLOY ORDER: reconcile.sql no longer writes the column, so it must be nullable before the new code
-- runs: execute the first DO block (DROP NOT NULL) first, deploy the code, then run the rest. Old code
-- (INSERT with normalized_data, reader in public_propositions.py) breaks once the column is dropped.
-- Rollback: db/rollbacks/0026_recreate_ingestion_entity_normalized_data.sql
SET lock_timeout = '10s';
SET statement_timeout = '120s';
DO $$ BEGIN
 IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'se_liga_brasil'
  AND table_name = 'ingestion_entity' AND column_name = 'normalized_data') THEN
  ALTER TABLE se_liga_brasil.ingestion_entity ALTER COLUMN normalized_data DROP NOT NULL;
 END IF;
END $$;
DO $$ BEGIN IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'se_liga_brasil' AND table_name = 'ingestion_entity' AND column_name = 'normalized_data') THEN
UPDATE se_liga_brasil.ingestion_entity e SET normalized_data = NULL
FROM se_liga_brasil.source_record sr
WHERE sr.id = e.source_record_id AND e.normalized_data IS NOT NULL
 AND sr.payload = e.normalized_data AND e.id > 0 AND e.id <= 50000;
END IF; END $$;
DO $$ BEGIN IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'se_liga_brasil' AND table_name = 'ingestion_entity' AND column_name = 'normalized_data') THEN
UPDATE se_liga_brasil.ingestion_entity e SET normalized_data = NULL
FROM se_liga_brasil.source_record sr
WHERE sr.id = e.source_record_id AND e.normalized_data IS NOT NULL
 AND sr.payload = e.normalized_data AND e.id > 50000 AND e.id <= 100000;
END IF; END $$;
DO $$ BEGIN IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'se_liga_brasil' AND table_name = 'ingestion_entity' AND column_name = 'normalized_data') THEN
UPDATE se_liga_brasil.ingestion_entity e SET normalized_data = NULL
FROM se_liga_brasil.source_record sr
WHERE sr.id = e.source_record_id AND e.normalized_data IS NOT NULL
 AND sr.payload = e.normalized_data AND e.id > 100000 AND e.id <= 150000;
END IF; END $$;
DO $$ BEGIN IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'se_liga_brasil' AND table_name = 'ingestion_entity' AND column_name = 'normalized_data') THEN
UPDATE se_liga_brasil.ingestion_entity e SET normalized_data = NULL
FROM se_liga_brasil.source_record sr
WHERE sr.id = e.source_record_id AND e.normalized_data IS NOT NULL
 AND sr.payload = e.normalized_data AND e.id > 150000 AND e.id <= 200000;
END IF; END $$;
DO $$ BEGIN IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'se_liga_brasil' AND table_name = 'ingestion_entity' AND column_name = 'normalized_data') THEN
UPDATE se_liga_brasil.ingestion_entity e SET normalized_data = NULL
FROM se_liga_brasil.source_record sr
WHERE sr.id = e.source_record_id AND e.normalized_data IS NOT NULL
 AND sr.payload = e.normalized_data AND e.id > 200000 AND e.id <= 250000;
END IF; END $$;
DO $$ BEGIN IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'se_liga_brasil' AND table_name = 'ingestion_entity' AND column_name = 'normalized_data') THEN
UPDATE se_liga_brasil.ingestion_entity e SET normalized_data = NULL
FROM se_liga_brasil.source_record sr
WHERE sr.id = e.source_record_id AND e.normalized_data IS NOT NULL
 AND sr.payload = e.normalized_data AND e.id > 250000 AND e.id <= 300000;
END IF; END $$;
DO $$ BEGIN IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'se_liga_brasil' AND table_name = 'ingestion_entity' AND column_name = 'normalized_data') THEN
UPDATE se_liga_brasil.ingestion_entity e SET normalized_data = NULL
FROM se_liga_brasil.source_record sr
WHERE sr.id = e.source_record_id AND e.normalized_data IS NOT NULL
 AND sr.payload = e.normalized_data AND e.id > 300000 AND e.id <= 350000;
END IF; END $$;
DO $$ BEGIN IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'se_liga_brasil' AND table_name = 'ingestion_entity' AND column_name = 'normalized_data') THEN
UPDATE se_liga_brasil.ingestion_entity e SET normalized_data = NULL
FROM se_liga_brasil.source_record sr
WHERE sr.id = e.source_record_id AND e.normalized_data IS NOT NULL
 AND sr.payload = e.normalized_data AND e.id > 350000 AND e.id <= 400000;
END IF; END $$;
DO $$ BEGIN IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'se_liga_brasil' AND table_name = 'ingestion_entity' AND column_name = 'normalized_data') THEN
UPDATE se_liga_brasil.ingestion_entity e SET normalized_data = NULL
FROM se_liga_brasil.source_record sr
WHERE sr.id = e.source_record_id AND e.normalized_data IS NOT NULL
 AND sr.payload = e.normalized_data AND e.id > 400000 AND e.id <= 450000;
END IF; END $$;
DO $$ BEGIN IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'se_liga_brasil' AND table_name = 'ingestion_entity' AND column_name = 'normalized_data') THEN
UPDATE se_liga_brasil.ingestion_entity e SET normalized_data = NULL
FROM se_liga_brasil.source_record sr
WHERE sr.id = e.source_record_id AND e.normalized_data IS NOT NULL
 AND sr.payload = e.normalized_data AND e.id > 450000 AND e.id <= 500000;
END IF; END $$;
DO $$ BEGIN IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'se_liga_brasil' AND table_name = 'ingestion_entity' AND column_name = 'normalized_data') THEN
UPDATE se_liga_brasil.ingestion_entity e SET normalized_data = NULL
FROM se_liga_brasil.source_record sr
WHERE sr.id = e.source_record_id AND e.normalized_data IS NOT NULL
 AND sr.payload = e.normalized_data AND e.id > 500000 AND e.id <= 550000;
END IF; END $$;
DO $$ BEGIN IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'se_liga_brasil' AND table_name = 'ingestion_entity' AND column_name = 'normalized_data') THEN
UPDATE se_liga_brasil.ingestion_entity e SET normalized_data = NULL
FROM se_liga_brasil.source_record sr
WHERE sr.id = e.source_record_id AND e.normalized_data IS NOT NULL
 AND sr.payload = e.normalized_data AND e.id > 550000 AND e.id <= 600000;
END IF; END $$;
DO $$ BEGIN IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'se_liga_brasil' AND table_name = 'ingestion_entity' AND column_name = 'normalized_data') THEN
UPDATE se_liga_brasil.ingestion_entity e SET normalized_data = NULL
FROM se_liga_brasil.source_record sr
WHERE sr.id = e.source_record_id AND e.normalized_data IS NOT NULL
 AND sr.payload = e.normalized_data AND e.id > 600000;
END IF; END $$;
DO $$ DECLARE remaining bigint; BEGIN
 IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'se_liga_brasil'
  AND table_name = 'ingestion_entity' AND column_name = 'normalized_data') THEN
  SELECT count(*) INTO remaining FROM se_liga_brasil.ingestion_entity WHERE normalized_data IS NOT NULL;
  IF remaining > 0 THEN
   RAISE EXCEPTION '% ingestion_entity rows differ from source_record.payload (or payload is NULL); column kept', remaining;
  END IF;
  ALTER TABLE se_liga_brasil.ingestion_entity DROP COLUMN normalized_data;
 END IF;
END $$;
