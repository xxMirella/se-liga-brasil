-- Rollback of 0030_drop_person_activity_context.sql: recreates the EMPTY table exactly as in
-- 0004_identity_and_affiliation.sql, with RLS enabled and no PUBLIC grants (the feed index was
-- dropped earlier by 0024 and is not recreated). Idempotent.
-- PENDING: not applied. Rows must be reloaded from the archive made before 0030, in this order of
-- dependencies: source, person, political_party, political_party_affiliation, electoral_candidacy,
-- office_term, source_record (all FK parents already exist in production).
-- After a reload the removed ingestion code (git history: db/ingestion/activity_context.sql,
-- database/activity_context.py, service/activity_context) would also have to be restored.
BEGIN;
SET LOCAL lock_timeout = '10s';
CREATE TABLE IF NOT EXISTS se_liga_brasil.person_activity_context (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 source_id bigint NOT NULL REFERENCES se_liga_brasil.source,
 activity_kind text NOT NULL,
 external_key text NOT NULL,
 person_id uuid NOT NULL REFERENCES se_liga_brasil.person,
 role text NOT NULL DEFAULT 'subject',
 political_party_id bigint REFERENCES se_liga_brasil.political_party,
 political_party_affiliation_id bigint REFERENCES se_liga_brasil.political_party_affiliation,
 electoral_candidacy_id bigint REFERENCES se_liga_brasil.electoral_candidacy,
 office_term_id bigint REFERENCES se_liga_brasil.office_term,
 claimed_office_code text,
 context_kind text NOT NULL CHECK(context_kind IN ('electoral_declaration','administrative')),
 occurred_at timestamptz,
 observed_at timestamptz NOT NULL,
 source_record_id bigint NOT NULL REFERENCES se_liga_brasil.source_record,
 UNIQUE(source_id,activity_kind,external_key,person_id,role,source_record_id)
);
ALTER TABLE se_liga_brasil.person_activity_context ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE se_liga_brasil.person_activity_context FROM PUBLIC;
COMMIT;
