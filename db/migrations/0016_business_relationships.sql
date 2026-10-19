BEGIN;
SET LOCAL lock_timeout='10s';
CREATE TABLE IF NOT EXISTS se_liga_brasil.business (
 company_base text PRIMARY KEY CHECK(company_base ~ '^[A-Z0-9]{8}$'),
 legal_name text,
 legal_nature_code text,
 share_capital numeric(20,2),
 size_code text,
 snapshot_month date NOT NULL,
 observed_on date NOT NULL,
 source_record_id bigint NOT NULL REFERENCES se_liga_brasil.source_record(id)
);
CREATE TABLE IF NOT EXISTS se_liga_brasil.business_establishment (
 cnpj text PRIMARY KEY CHECK(cnpj ~ '^[A-Z0-9]{12}[0-9]{2}$'),
 company_base text NOT NULL REFERENCES se_liga_brasil.business(company_base),
 trade_name text,
 headquarters_code text,
 registration_status_code text,
 registration_status_date date,
 activity_started_on date,
 primary_activity_code text,
 uf text,
 municipality_code text,
 snapshot_month date NOT NULL,
 observed_on date NOT NULL,
 source_record_id bigint NOT NULL REFERENCES se_liga_brasil.source_record(id)
);
CREATE TABLE IF NOT EXISTS se_liga_brasil.person_business_relationship_observation (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 person_id uuid NOT NULL REFERENCES se_liga_brasil.person(id),
 company_base text NOT NULL REFERENCES se_liga_brasil.business(company_base),
 qualification_code text NOT NULL,
 entered_on date,
 exited_on date,
 snapshot_month date NOT NULL,
 observed_on date NOT NULL,
 identity_evidence_url text NOT NULL,
 reviewed_by text NOT NULL,
 reviewed_at timestamptz NOT NULL,
 source_record_id bigint NOT NULL REFERENCES se_liga_brasil.source_record(id),
 UNIQUE(person_id,company_base,qualification_code,source_record_id),
 CHECK(exited_on IS NULL OR entered_on IS NULL OR exited_on >= entered_on)
);
CREATE INDEX IF NOT EXISTS person_business_observation_person_date_idx
 ON se_liga_brasil.person_business_relationship_observation(person_id,observed_on DESC);
CREATE INDEX IF NOT EXISTS business_establishment_company_idx
 ON se_liga_brasil.business_establishment(company_base);
CREATE INDEX IF NOT EXISTS business_relationship_company_idx
 ON se_liga_brasil.person_business_relationship_observation(company_base);
ALTER TABLE se_liga_brasil.business ENABLE ROW LEVEL SECURITY;
ALTER TABLE se_liga_brasil.business_establishment ENABLE ROW LEVEL SECURITY;
ALTER TABLE se_liga_brasil.person_business_relationship_observation ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON se_liga_brasil.business,se_liga_brasil.business_establishment,
 se_liga_brasil.person_business_relationship_observation FROM PUBLIC;
DO $$ DECLARE role_name text; BEGIN
 FOREACH role_name IN ARRAY ARRAY['anon','authenticated'] LOOP
  IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname=role_name) THEN
   EXECUTE format('REVOKE ALL ON se_liga_brasil.business,se_liga_brasil.business_establishment,se_liga_brasil.person_business_relationship_observation FROM %I',role_name);
  END IF;
 END LOOP;
END $$;
COMMENT ON TABLE se_liga_brasil.person_business_relationship_observation IS
 'Reviewed QSA observations, not complete historical membership; snapshot absence never proves exit.';
COMMIT;
