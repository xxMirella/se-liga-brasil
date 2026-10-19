BEGIN;
CREATE TABLE IF NOT EXISTS se_liga_brasil.person_career_coverage_receipt (
 person_id uuid NOT NULL REFERENCES se_liga_brasil.person(id),
 institution text NOT NULL, domain text NOT NULL, source text NOT NULL,
 partition_key text NOT NULL, starts_on date NOT NULL, ends_before date NOT NULL,
 checked_on date NOT NULL, identity_verified boolean NOT NULL,
 enumeration_complete boolean NOT NULL, source_period_complete boolean NOT NULL,
 artifact_verified boolean NOT NULL, scope_verified boolean NOT NULL,
 artifact_sha256 text NOT NULL CHECK (artifact_sha256 ~ '^[a-f0-9]{64}$'),
 parser_version text NOT NULL CHECK (length(parser_version)>0),
 acquisition_status text NOT NULL CHECK (acquisition_status IN ('available','unavailable')),
 PRIMARY KEY(person_id,institution,domain,source,partition_key,starts_on,ends_before),
 CHECK (ends_before>starts_on)
);
ALTER TABLE se_liga_brasil.person_career_coverage_receipt ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON se_liga_brasil.person_career_coverage_receipt FROM PUBLIC;
DO $$ DECLARE role_name text; BEGIN
 FOREACH role_name IN ARRAY ARRAY['anon','authenticated'] LOOP
  IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname=role_name) THEN
   EXECUTE format('REVOKE ALL ON se_liga_brasil.person_career_coverage_receipt FROM %I',role_name);
  END IF;
 END LOOP;
END $$;
COMMIT;
