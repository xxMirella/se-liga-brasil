BEGIN;
SET LOCAL lock_timeout='10s';
SET LOCAL statement_timeout='120s';
CREATE TABLE se_liga_brasil.person_payroll_payment (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 entity_id bigint NOT NULL UNIQUE REFERENCES se_liga_brasil.ingestion_entity,
 source_id bigint NOT NULL REFERENCES se_liga_brasil.source,
 recipient_key text NOT NULL,
 recipient_name text NOT NULL,
 normalized_recipient_name text NOT NULL,
 person_id uuid REFERENCES se_liga_brasil.person,
 identity_status text NOT NULL DEFAULT 'pending' CHECK(identity_status IN ('pending','verified')),
 office_exercise_id bigint REFERENCES se_liga_brasil.office_exercise,
 organization_code text NOT NULL,
 office_kind text NOT NULL,
 represented_uf text NOT NULL,
 competence date NOT NULL CHECK(extract(day FROM competence)=1),
 currency text NOT NULL CHECK(currency='BRL'),
 payroll_kind text NOT NULL,
 gross_amount numeric(20,2) NOT NULL,
 tax_amount numeric(20,2) NOT NULL,
 net_amount numeric(20,2) NOT NULL,
 source_record_id bigint NOT NULL REFERENCES se_liga_brasil.source_record,
 observed_at timestamptz NOT NULL,
 updated_at timestamptz NOT NULL DEFAULT now(),
 CHECK(gross_amount-tax_amount=net_amount),
 CHECK((person_id IS NULL AND identity_status='pending') OR
       (person_id IS NOT NULL AND identity_status='verified')),
 UNIQUE(source_id,organization_code,recipient_key,competence,payroll_kind)
);
COMMENT ON TABLE se_liga_brasil.person_payroll_payment IS
 'Published payroll facts. Unresolved recipients are preserved without guessing a person. Immutable history lives in ingestion_entity_version.';
CREATE INDEX payroll_person_competence_idx ON se_liga_brasil.person_payroll_payment(person_id,competence DESC);
CREATE INDEX payroll_source_record_idx ON se_liga_brasil.person_payroll_payment(source_record_id);
CREATE INDEX payroll_source_idx ON se_liga_brasil.person_payroll_payment(source_id);
CREATE INDEX payroll_exercise_idx ON se_liga_brasil.person_payroll_payment(office_exercise_id);
CREATE INDEX payroll_pending_identity_idx ON se_liga_brasil.person_payroll_payment(normalized_recipient_name)
 WHERE identity_status='pending';
ALTER TABLE se_liga_brasil.person_payroll_payment ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE se_liga_brasil.person_payroll_payment FROM PUBLIC;
COMMIT;
