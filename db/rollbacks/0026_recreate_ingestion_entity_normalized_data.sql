-- Rollback of 0026_drop_ingestion_entity_normalized_data.sql. Idempotent; run with autocommit (psql -f).
-- Re-adds ingestion_entity.normalized_data and refills it from source_record.payload of the row that
-- source_record_id points to, in id ranges of 50,000 rows. SET NOT NULL runs only if no row is left NULL
-- (it stays nullable otherwise, e.g. when source_record.payload was archived).
SET lock_timeout = '10s';
SET statement_timeout = '120s';
ALTER TABLE se_liga_brasil.ingestion_entity ADD COLUMN IF NOT EXISTS normalized_data jsonb;
UPDATE se_liga_brasil.ingestion_entity e SET normalized_data = sr.payload
FROM se_liga_brasil.source_record sr
WHERE sr.id = e.source_record_id AND e.normalized_data IS NULL AND sr.payload IS NOT NULL AND e.id > 0 AND e.id <= 50000;
UPDATE se_liga_brasil.ingestion_entity e SET normalized_data = sr.payload
FROM se_liga_brasil.source_record sr
WHERE sr.id = e.source_record_id AND e.normalized_data IS NULL AND sr.payload IS NOT NULL AND e.id > 50000 AND e.id <= 100000;
UPDATE se_liga_brasil.ingestion_entity e SET normalized_data = sr.payload
FROM se_liga_brasil.source_record sr
WHERE sr.id = e.source_record_id AND e.normalized_data IS NULL AND sr.payload IS NOT NULL AND e.id > 100000 AND e.id <= 150000;
UPDATE se_liga_brasil.ingestion_entity e SET normalized_data = sr.payload
FROM se_liga_brasil.source_record sr
WHERE sr.id = e.source_record_id AND e.normalized_data IS NULL AND sr.payload IS NOT NULL AND e.id > 150000 AND e.id <= 200000;
UPDATE se_liga_brasil.ingestion_entity e SET normalized_data = sr.payload
FROM se_liga_brasil.source_record sr
WHERE sr.id = e.source_record_id AND e.normalized_data IS NULL AND sr.payload IS NOT NULL AND e.id > 200000 AND e.id <= 250000;
UPDATE se_liga_brasil.ingestion_entity e SET normalized_data = sr.payload
FROM se_liga_brasil.source_record sr
WHERE sr.id = e.source_record_id AND e.normalized_data IS NULL AND sr.payload IS NOT NULL AND e.id > 250000 AND e.id <= 300000;
UPDATE se_liga_brasil.ingestion_entity e SET normalized_data = sr.payload
FROM se_liga_brasil.source_record sr
WHERE sr.id = e.source_record_id AND e.normalized_data IS NULL AND sr.payload IS NOT NULL AND e.id > 300000 AND e.id <= 350000;
UPDATE se_liga_brasil.ingestion_entity e SET normalized_data = sr.payload
FROM se_liga_brasil.source_record sr
WHERE sr.id = e.source_record_id AND e.normalized_data IS NULL AND sr.payload IS NOT NULL AND e.id > 350000 AND e.id <= 400000;
UPDATE se_liga_brasil.ingestion_entity e SET normalized_data = sr.payload
FROM se_liga_brasil.source_record sr
WHERE sr.id = e.source_record_id AND e.normalized_data IS NULL AND sr.payload IS NOT NULL AND e.id > 400000 AND e.id <= 450000;
UPDATE se_liga_brasil.ingestion_entity e SET normalized_data = sr.payload
FROM se_liga_brasil.source_record sr
WHERE sr.id = e.source_record_id AND e.normalized_data IS NULL AND sr.payload IS NOT NULL AND e.id > 450000 AND e.id <= 500000;
UPDATE se_liga_brasil.ingestion_entity e SET normalized_data = sr.payload
FROM se_liga_brasil.source_record sr
WHERE sr.id = e.source_record_id AND e.normalized_data IS NULL AND sr.payload IS NOT NULL AND e.id > 500000 AND e.id <= 550000;
UPDATE se_liga_brasil.ingestion_entity e SET normalized_data = sr.payload
FROM se_liga_brasil.source_record sr
WHERE sr.id = e.source_record_id AND e.normalized_data IS NULL AND sr.payload IS NOT NULL AND e.id > 550000 AND e.id <= 600000;
UPDATE se_liga_brasil.ingestion_entity e SET normalized_data = sr.payload
FROM se_liga_brasil.source_record sr
WHERE sr.id = e.source_record_id AND e.normalized_data IS NULL AND sr.payload IS NOT NULL AND e.id > 600000;
DO $$ BEGIN
 IF NOT EXISTS (SELECT 1 FROM se_liga_brasil.ingestion_entity WHERE normalized_data IS NULL) THEN
  ALTER TABLE se_liga_brasil.ingestion_entity ALTER COLUMN normalized_data SET NOT NULL;
 ELSE
  RAISE WARNING 'Some ingestion_entity rows have no payload to restore; normalized_data left nullable';
 END IF;
END $$;
