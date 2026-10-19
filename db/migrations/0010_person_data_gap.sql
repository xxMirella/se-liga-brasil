BEGIN;
SET LOCAL lock_timeout='10s';
SET LOCAL statement_timeout='120s';
CREATE TABLE se_liga_brasil.person_data_gap (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 person_id uuid NOT NULL REFERENCES se_liga_brasil.person,
 field_name text NOT NULL,
 quality_state text NOT NULL,
 assigned_source text CHECK(assigned_source IN ('tse','alesp','camara')),
 status text NOT NULL DEFAULT 'queued' CHECK(status IN ('queued','running','resolved','blocked')),
 first_detected_at timestamptz NOT NULL DEFAULT now(),
 last_checked_at timestamptz NOT NULL DEFAULT now(),
 last_assessment_id uuid NOT NULL,
 next_attempt_at timestamptz NOT NULL DEFAULT now(),
 attempts integer NOT NULL DEFAULT 0 CHECK(attempts>=0),
 claimed_by uuid,
 lease_until timestamptz,
 resolved_at timestamptz,
 last_error_code text,
 UNIQUE(person_id,field_name),
 CHECK((status='running' AND claimed_by IS NOT NULL AND lease_until IS NOT NULL)
   OR (status<>'running' AND claimed_by IS NULL AND lease_until IS NULL))
);
CREATE INDEX person_data_gap_due_idx ON se_liga_brasil.person_data_gap(assigned_source,next_attempt_at,id)
 WHERE status IN ('queued','running');
CREATE INDEX person_data_gap_person_idx ON se_liga_brasil.person_data_gap(person_id,status);
ALTER TABLE se_liga_brasil.person_data_gap ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON se_liga_brasil.person_data_gap FROM PUBLIC;
COMMENT ON TABLE se_liga_brasil.person_data_gap IS
 'Persistent required-data gaps. Completeness assesses facts; orchestration routes and leases collection.';
COMMIT;
