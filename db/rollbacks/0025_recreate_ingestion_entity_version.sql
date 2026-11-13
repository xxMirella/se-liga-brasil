-- Rollback of 0025_drop_ingestion_entity_version.sql. Idempotent; run with autocommit (psql -f).
-- Replaces the compatibility view by the physical table (same definition as 0003, without the
-- source_record index that 0024 dropped) and refills it from source_record in id ranges of 50,000
-- entities. first_ingested_at is restored as source_record.fetched_at (approximation); load the exact
-- values of the ~151 multi-version entities from the 0025 archive afterwards.
-- Fails loudly (NOT NULL) if source_record.payload was archived before this rollback.
SET lock_timeout = '10s';
SET statement_timeout = '120s';
DO $$ BEGIN
 IF (SELECT c.relkind FROM pg_class c WHERE c.oid = to_regclass('se_liga_brasil.ingestion_entity_version')) = 'v' THEN
  DROP VIEW se_liga_brasil.ingestion_entity_version;
 END IF;
END $$;
CREATE TABLE IF NOT EXISTS se_liga_brasil.ingestion_entity_version (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 entity_id bigint NOT NULL REFERENCES se_liga_brasil.ingestion_entity,
 content_sha256 text NOT NULL,
 normalized_data jsonb NOT NULL,
 source_record_id bigint NOT NULL REFERENCES se_liga_brasil.source_record,
 first_ingested_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(entity_id,content_sha256)
);
ALTER TABLE se_liga_brasil.ingestion_entity_version ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE se_liga_brasil.ingestion_entity_version FROM PUBLIC;
INSERT INTO se_liga_brasil.ingestion_entity_version(entity_id,content_sha256,normalized_data,source_record_id,first_ingested_at)
SELECT e.id, sr.content_sha256, sr.payload, sr.id, sr.fetched_at
FROM se_liga_brasil.ingestion_entity e
JOIN se_liga_brasil.source_record sr ON sr.source_id = e.source_id
 AND sr.external_key = e.entity_kind || ':' || e.external_key
WHERE e.id > 0 AND e.id <= 50000
ON CONFLICT (entity_id, content_sha256) DO NOTHING;
INSERT INTO se_liga_brasil.ingestion_entity_version(entity_id,content_sha256,normalized_data,source_record_id,first_ingested_at)
SELECT e.id, sr.content_sha256, sr.payload, sr.id, sr.fetched_at
FROM se_liga_brasil.ingestion_entity e
JOIN se_liga_brasil.source_record sr ON sr.source_id = e.source_id
 AND sr.external_key = e.entity_kind || ':' || e.external_key
WHERE e.id > 50000 AND e.id <= 100000
ON CONFLICT (entity_id, content_sha256) DO NOTHING;
INSERT INTO se_liga_brasil.ingestion_entity_version(entity_id,content_sha256,normalized_data,source_record_id,first_ingested_at)
SELECT e.id, sr.content_sha256, sr.payload, sr.id, sr.fetched_at
FROM se_liga_brasil.ingestion_entity e
JOIN se_liga_brasil.source_record sr ON sr.source_id = e.source_id
 AND sr.external_key = e.entity_kind || ':' || e.external_key
WHERE e.id > 100000 AND e.id <= 150000
ON CONFLICT (entity_id, content_sha256) DO NOTHING;
INSERT INTO se_liga_brasil.ingestion_entity_version(entity_id,content_sha256,normalized_data,source_record_id,first_ingested_at)
SELECT e.id, sr.content_sha256, sr.payload, sr.id, sr.fetched_at
FROM se_liga_brasil.ingestion_entity e
JOIN se_liga_brasil.source_record sr ON sr.source_id = e.source_id
 AND sr.external_key = e.entity_kind || ':' || e.external_key
WHERE e.id > 150000 AND e.id <= 200000
ON CONFLICT (entity_id, content_sha256) DO NOTHING;
INSERT INTO se_liga_brasil.ingestion_entity_version(entity_id,content_sha256,normalized_data,source_record_id,first_ingested_at)
SELECT e.id, sr.content_sha256, sr.payload, sr.id, sr.fetched_at
FROM se_liga_brasil.ingestion_entity e
JOIN se_liga_brasil.source_record sr ON sr.source_id = e.source_id
 AND sr.external_key = e.entity_kind || ':' || e.external_key
WHERE e.id > 200000 AND e.id <= 250000
ON CONFLICT (entity_id, content_sha256) DO NOTHING;
INSERT INTO se_liga_brasil.ingestion_entity_version(entity_id,content_sha256,normalized_data,source_record_id,first_ingested_at)
SELECT e.id, sr.content_sha256, sr.payload, sr.id, sr.fetched_at
FROM se_liga_brasil.ingestion_entity e
JOIN se_liga_brasil.source_record sr ON sr.source_id = e.source_id
 AND sr.external_key = e.entity_kind || ':' || e.external_key
WHERE e.id > 250000 AND e.id <= 300000
ON CONFLICT (entity_id, content_sha256) DO NOTHING;
INSERT INTO se_liga_brasil.ingestion_entity_version(entity_id,content_sha256,normalized_data,source_record_id,first_ingested_at)
SELECT e.id, sr.content_sha256, sr.payload, sr.id, sr.fetched_at
FROM se_liga_brasil.ingestion_entity e
JOIN se_liga_brasil.source_record sr ON sr.source_id = e.source_id
 AND sr.external_key = e.entity_kind || ':' || e.external_key
WHERE e.id > 300000 AND e.id <= 350000
ON CONFLICT (entity_id, content_sha256) DO NOTHING;
INSERT INTO se_liga_brasil.ingestion_entity_version(entity_id,content_sha256,normalized_data,source_record_id,first_ingested_at)
SELECT e.id, sr.content_sha256, sr.payload, sr.id, sr.fetched_at
FROM se_liga_brasil.ingestion_entity e
JOIN se_liga_brasil.source_record sr ON sr.source_id = e.source_id
 AND sr.external_key = e.entity_kind || ':' || e.external_key
WHERE e.id > 350000 AND e.id <= 400000
ON CONFLICT (entity_id, content_sha256) DO NOTHING;
INSERT INTO se_liga_brasil.ingestion_entity_version(entity_id,content_sha256,normalized_data,source_record_id,first_ingested_at)
SELECT e.id, sr.content_sha256, sr.payload, sr.id, sr.fetched_at
FROM se_liga_brasil.ingestion_entity e
JOIN se_liga_brasil.source_record sr ON sr.source_id = e.source_id
 AND sr.external_key = e.entity_kind || ':' || e.external_key
WHERE e.id > 400000 AND e.id <= 450000
ON CONFLICT (entity_id, content_sha256) DO NOTHING;
INSERT INTO se_liga_brasil.ingestion_entity_version(entity_id,content_sha256,normalized_data,source_record_id,first_ingested_at)
SELECT e.id, sr.content_sha256, sr.payload, sr.id, sr.fetched_at
FROM se_liga_brasil.ingestion_entity e
JOIN se_liga_brasil.source_record sr ON sr.source_id = e.source_id
 AND sr.external_key = e.entity_kind || ':' || e.external_key
WHERE e.id > 450000 AND e.id <= 500000
ON CONFLICT (entity_id, content_sha256) DO NOTHING;
INSERT INTO se_liga_brasil.ingestion_entity_version(entity_id,content_sha256,normalized_data,source_record_id,first_ingested_at)
SELECT e.id, sr.content_sha256, sr.payload, sr.id, sr.fetched_at
FROM se_liga_brasil.ingestion_entity e
JOIN se_liga_brasil.source_record sr ON sr.source_id = e.source_id
 AND sr.external_key = e.entity_kind || ':' || e.external_key
WHERE e.id > 500000 AND e.id <= 550000
ON CONFLICT (entity_id, content_sha256) DO NOTHING;
INSERT INTO se_liga_brasil.ingestion_entity_version(entity_id,content_sha256,normalized_data,source_record_id,first_ingested_at)
SELECT e.id, sr.content_sha256, sr.payload, sr.id, sr.fetched_at
FROM se_liga_brasil.ingestion_entity e
JOIN se_liga_brasil.source_record sr ON sr.source_id = e.source_id
 AND sr.external_key = e.entity_kind || ':' || e.external_key
WHERE e.id > 550000 AND e.id <= 600000
ON CONFLICT (entity_id, content_sha256) DO NOTHING;
INSERT INTO se_liga_brasil.ingestion_entity_version(entity_id,content_sha256,normalized_data,source_record_id,first_ingested_at)
SELECT e.id, sr.content_sha256, sr.payload, sr.id, sr.fetched_at
FROM se_liga_brasil.ingestion_entity e
JOIN se_liga_brasil.source_record sr ON sr.source_id = e.source_id
 AND sr.external_key = e.entity_kind || ':' || e.external_key
WHERE e.id > 600000
ON CONFLICT (entity_id, content_sha256) DO NOTHING;
