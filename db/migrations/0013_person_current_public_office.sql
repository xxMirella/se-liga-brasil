BEGIN;
SET LOCAL lock_timeout='10s';
SET LOCAL statement_timeout='120s';
ALTER TABLE se_liga_brasil.person
 ADD COLUMN has_current_public_office boolean,
 ADD COLUMN current_public_office_kind text,
 ADD COLUMN current_public_office_institution_id bigint REFERENCES se_liga_brasil.institution,
 ADD COLUMN current_public_office_term_id bigint REFERENCES se_liga_brasil.office_term,
 ADD COLUMN public_office_status_as_of date,
 ADD COLUMN public_office_status_source_record_id bigint REFERENCES se_liga_brasil.source_record,
 ADD CONSTRAINT person_current_public_office_state_check CHECK(
  (has_current_public_office IS TRUE AND current_public_office_kind IS NOT NULL
   AND current_public_office_institution_id IS NOT NULL
   AND public_office_status_source_record_id IS NOT NULL AND public_office_status_as_of IS NOT NULL)
  OR (has_current_public_office IS FALSE AND current_public_office_kind IS NULL
   AND current_public_office_institution_id IS NULL AND current_public_office_term_id IS NULL
   AND public_office_status_source_record_id IS NOT NULL AND public_office_status_as_of IS NOT NULL)
  OR (has_current_public_office IS NULL AND current_public_office_kind IS NULL
   AND current_public_office_institution_id IS NULL AND current_public_office_term_id IS NULL
   AND public_office_status_source_record_id IS NULL));
COMMENT ON COLUMN se_liga_brasil.person.has_current_public_office IS
 'True: verified current exercise; false: explicit verified absence across public offices; NULL: unknown.';
COMMENT ON COLUMN se_liga_brasil.person.current_public_office_kind IS
 'Current verified office kind; historical candidacy does not establish current exercise.';
CREATE INDEX person_current_public_office_institution_idx
 ON se_liga_brasil.person(current_public_office_institution_id)
 WHERE has_current_public_office IS TRUE;
COMMIT;
