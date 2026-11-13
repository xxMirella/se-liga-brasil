-- Storage (R6): drop se_liga_brasil.person_activity_context (about 38 MB; 105k rows, 100% TSE).
-- PENDING: not applied. Not wired to db-migrate or operations.py. Idempotent; rollback in
-- db/rollbacks/0030_recreate_person_activity_context.sql (structure only; data comes from the archive).
--
-- Why it is safe: nothing in src/, db/, scripts/ or app.py reads the table (only INSERTs from the
-- removed db/ingestion/activity_context.sql and database/activity_context.py). Person, political
-- party and office code are derivable from electoral_candidacy (5251/5251) and the party
-- affiliation from political_party_affiliation (5173/5251), joined by (source, election_year,
-- candidate_sequence); the row-level source_record_id is kept in the archive.
--
-- PRECONDITION (do not skip): archive the rows first with the archive_* exporter and validate the
-- count and checksum. The DROP below is irreversible without that archive. This file does not check it.
--
-- Also drops: its FK constraints, unique key, and the feed index (already dropped by 0024). No
-- view, trigger or function depends on it; merge_person_identity discovers person FKs dynamically
-- and simply stops seeing this table.
-- Space returns to the database immediately (DROP TABLE); no VACUUM FULL needed.
BEGIN;
SET LOCAL lock_timeout = '10s';
DROP TABLE IF EXISTS se_liga_brasil.person_activity_context;
COMMIT;
