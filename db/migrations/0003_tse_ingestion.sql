BEGIN;
SET LOCAL lock_timeout='5s';
SET LOCAL statement_timeout='60s';
CREATE TABLE se_liga_brasil.ingestion_run (
 id uuid PRIMARY KEY,
 started_at timestamptz NOT NULL DEFAULT now(),
 finished_at timestamptz,
 status text NOT NULL CHECK(status IN ('running','completed','partial','failed','interrupted')),
 configuration jsonb NOT NULL,
 summary jsonb NOT NULL DEFAULT '{}'
);
CREATE TABLE se_liga_brasil.ingestion_artifact (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 source_id bigint NOT NULL REFERENCES se_liga_brasil.source,
 resource_id text NOT NULL,
 dataset_name text NOT NULL,
 resource_kind text NOT NULL,
 source_url text NOT NULL CHECK(source_url ~ '^https://'),
 content_sha256 text NOT NULL CHECK(content_sha256 ~ '^[a-f0-9]{64}$'),
 storage_reference text NOT NULL,
 fetched_at timestamptz NOT NULL,
 parser_version text NOT NULL,
 scope_key text NOT NULL,
 status text NOT NULL CHECK(status IN ('ingesting','completed','partial')),
 ingested_at timestamptz,
 summary jsonb NOT NULL DEFAULT '{}',
 UNIQUE(source_id,resource_id,content_sha256,parser_version,scope_key)
);
CREATE TABLE se_liga_brasil.ingestion_entity (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 source_id bigint NOT NULL REFERENCES se_liga_brasil.source,
 entity_kind text NOT NULL,
 external_key text NOT NULL,
 content_sha256 text NOT NULL CHECK(content_sha256 ~ '^[a-f0-9]{64}$'),
 normalized_data jsonb NOT NULL,
 source_record_id bigint NOT NULL REFERENCES se_liga_brasil.source_record,
 source_generated_at timestamptz NOT NULL,
 first_ingested_at timestamptz NOT NULL DEFAULT now(),
 last_ingested_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(source_id,entity_kind,external_key)
);
CREATE TABLE se_liga_brasil.ingestion_entity_version (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 entity_id bigint NOT NULL REFERENCES se_liga_brasil.ingestion_entity,
 content_sha256 text NOT NULL,
 normalized_data jsonb NOT NULL,
 source_record_id bigint NOT NULL REFERENCES se_liga_brasil.source_record,
 first_ingested_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(entity_id,content_sha256)
);
CREATE TABLE se_liga_brasil.ingestion_artifact_entity (
 artifact_id bigint NOT NULL REFERENCES se_liga_brasil.ingestion_artifact,
 entity_id bigint NOT NULL REFERENCES se_liga_brasil.ingestion_entity,
 source_record_id bigint NOT NULL REFERENCES se_liga_brasil.source_record,
 PRIMARY KEY(artifact_id,entity_id)
);
CREATE TABLE se_liga_brasil.ingestion_rejection (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 run_id uuid NOT NULL REFERENCES se_liga_brasil.ingestion_run,
 artifact_id bigint REFERENCES se_liga_brasil.ingestion_artifact,
 resource_id text NOT NULL,
 entry_name text,
 row_number integer,
 reason_code text NOT NULL,
 payload_sha256 text,
 details jsonb NOT NULL DEFAULT '{}',
 rejected_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE se_liga_brasil.electoral_candidacy (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 source_id bigint NOT NULL REFERENCES se_liga_brasil.source,
 external_key text NOT NULL,
 person_id uuid NOT NULL REFERENCES se_liga_brasil.person,
 election_year integer NOT NULL CHECK(election_year BETWEEN 1945 AND 2200),
 election_id text NOT NULL,
 candidate_sequence text NOT NULL CHECK(candidate_sequence ~ '^[0-9]+$'),
 election_round integer NOT NULL CHECK(election_round BETWEEN 1 AND 3),
 represented_uf text NOT NULL CHECK(represented_uf IN ('AC','AL','AP','AM','BA','CE','DF','ES','GO','MA','MT','MS','MG','PA','PB','PE','PI','PR','RJ','RN','RS','RO','RR','SC','SP','SE','TO','BR','ZZ')),
 office_code text NOT NULL,
 office_name text NOT NULL,
 political_party_code text,
 political_party_name text,
 political_party_abbreviation text,
 candidacy_status text,
 election_result text,
 source_record_id bigint NOT NULL REFERENCES se_liga_brasil.source_record,
 source_generated_at timestamptz NOT NULL,
 ingested_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(source_id,external_key)
);
CREATE INDEX electoral_candidacy_person_history_idx ON se_liga_brasil.electoral_candidacy(person_id,election_year DESC);
CREATE INDEX electoral_candidacy_sequence_idx ON se_liga_brasil.electoral_candidacy(source_id,election_year,candidate_sequence);
CREATE TABLE se_liga_brasil.candidate_asset_declaration (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 entity_id bigint NOT NULL UNIQUE REFERENCES se_liga_brasil.ingestion_entity,
 person_id uuid NOT NULL REFERENCES se_liga_brasil.person,
 election_year integer NOT NULL,
 candidate_sequence text NOT NULL,
 asset_order text NOT NULL,
 asset_type text NOT NULL,
 description text,
 declared_value numeric(20,2) NOT NULL CHECK(declared_value>=0),
 source_record_id bigint NOT NULL REFERENCES se_liga_brasil.source_record,
 source_generated_at timestamptz NOT NULL,
 ingested_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX candidate_asset_person_year_idx ON se_liga_brasil.candidate_asset_declaration(person_id,election_year);
CREATE TABLE se_liga_brasil.candidate_document (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 entity_id bigint NOT NULL UNIQUE REFERENCES se_liga_brasil.ingestion_entity,
 person_id uuid NOT NULL REFERENCES se_liga_brasil.person,
 election_year integer NOT NULL,
 candidate_sequence text NOT NULL,
 document_kind text NOT NULL CHECK(document_kind IN ('government_proposal','criminal_certificate')),
 original_entry_name text NOT NULL,
 storage_reference text NOT NULL,
 content_sha256 text NOT NULL CHECK(content_sha256 ~ '^[a-f0-9]{64}$'),
 interpretation_status text NOT NULL DEFAULT 'not_analyzed' CHECK(interpretation_status='not_analyzed'),
 source_record_id bigint NOT NULL REFERENCES se_liga_brasil.source_record,
 source_generated_at timestamptz NOT NULL,
 ingested_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX candidate_document_person_idx ON se_liga_brasil.candidate_document(person_id,election_year,document_kind);
-- Provenance lives in source_record and immutable ingestion_entity_version; only validated data reaches projections.
DO $$ DECLARE item record; BEGIN
 FOR item IN SELECT t.oid,t.relname FROM pg_class t JOIN pg_namespace n ON n.oid=t.relnamespace WHERE n.nspname='se_liga_brasil' AND t.relkind='r' LOOP
  EXECUTE format('ALTER TABLE se_liga_brasil.%I ENABLE ROW LEVEL SECURITY',item.relname);
  EXECUTE format('REVOKE ALL ON TABLE se_liga_brasil.%I FROM PUBLIC',item.relname);
 END LOOP;
 FOR item IN SELECT t.relname,a.attname,a.attnum,c.conrelid FROM pg_constraint c JOIN pg_class t ON t.oid=c.conrelid JOIN pg_namespace n ON n.oid=t.relnamespace JOIN pg_attribute a ON a.attrelid=c.conrelid AND a.attnum=c.conkey[1] WHERE n.nspname='se_liga_brasil' AND c.contype='f' LOOP
  IF NOT EXISTS(SELECT 1 FROM pg_index i WHERE i.indrelid=item.conrelid AND i.indisvalid AND i.indkey[0]=item.attnum) THEN
   EXECUTE format('CREATE INDEX %I ON se_liga_brasil.%I (%I)',item.relname||'_'||item.attname||'_idx',item.relname,item.attname);
  END IF;
 END LOOP;
END $$;
COMMIT;
