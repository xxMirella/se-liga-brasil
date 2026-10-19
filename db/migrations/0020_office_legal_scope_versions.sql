BEGIN;
CREATE TABLE IF NOT EXISTS se_liga_brasil.office_legal_scope_version (
 office_kind text NOT NULL CHECK(length(office_kind)>0),
 jurisdiction text NOT NULL CHECK(length(jurisdiction)>0),
 catalog_version text NOT NULL CHECK(length(catalog_version)>0),
 reviewed_on date NOT NULL,
 legal_valid_from date,
 legal_valid_until date,
 coverage_status text NOT NULL CHECK(coverage_status IN
   ('reviewed_baseline','local_law_required','unclassified')),
 competencies jsonb NOT NULL CHECK(jsonb_typeof(competencies)='array'),
 restrictions jsonb NOT NULL CHECK(jsonb_typeof(restrictions)='array'),
 sources jsonb NOT NULL CHECK(jsonb_typeof(sources)='array'),
 limitations text[] NOT NULL,
 content_sha256 text NOT NULL CHECK(content_sha256 ~ '^[a-f0-9]{64}$'),
 created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(office_kind,jurisdiction,catalog_version),
 CHECK(legal_valid_from IS NULL OR legal_valid_until IS NULL
   OR legal_valid_until>legal_valid_from)
);
ALTER TABLE se_liga_brasil.office_legal_scope_version ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON se_liga_brasil.office_legal_scope_version FROM PUBLIC;
DO $$ DECLARE role_name text; BEGIN
 FOREACH role_name IN ARRAY ARRAY['anon','authenticated'] LOOP
  IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname=role_name) THEN
   EXECUTE format('REVOKE ALL ON se_liga_brasil.office_legal_scope_version FROM %I',role_name);
  END IF;
 END LOOP;
END $$;
COMMENT ON TABLE se_liga_brasil.office_legal_scope_version IS
 'Versioned documentary baseline; unknown legal validity is not inferred from review date. '
 'Append-only through the application repository; same-key hash conflicts are rejected.';
COMMIT;
