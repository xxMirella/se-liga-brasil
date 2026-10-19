BEGIN;
SET LOCAL lock_timeout='10s';
ALTER TABLE se_liga_brasil.voting ALTER COLUMN held_at DROP NOT NULL;
ALTER TABLE se_liga_brasil.voting ADD COLUMN IF NOT EXISTS held_on date;
ALTER TABLE se_liga_brasil.voting ADD COLUMN IF NOT EXISTS date_precision text NOT NULL DEFAULT 'instant';
ALTER TABLE se_liga_brasil.voting ADD COLUMN IF NOT EXISTS legislative_body_code text;
ALTER TABLE se_liga_brasil.voting ADD COLUMN IF NOT EXISTS session_key text;
ALTER TABLE se_liga_brasil.voting ADD COLUMN IF NOT EXISTS sequence_number integer;
ALTER TABLE se_liga_brasil.voting ADD COLUMN IF NOT EXISTS round_number integer;
ALTER TABLE se_liga_brasil.voting ADD COLUMN IF NOT EXISTS subject_kind text NOT NULL DEFAULT 'unknown';
ALTER TABLE se_liga_brasil.voting ADD COLUMN IF NOT EXISTS stage text NOT NULL DEFAULT 'unknown';
ALTER TABLE se_liga_brasil.voting ADD COLUMN IF NOT EXISTS nominal_availability text NOT NULL DEFAULT 'unknown';
ALTER TABLE se_liga_brasil.voting ADD COLUMN IF NOT EXISTS collective_result_code text;
UPDATE se_liga_brasil.voting SET held_on=(held_at AT TIME ZONE 'America/Sao_Paulo')::date WHERE held_on IS NULL AND held_at IS NOT NULL;
ALTER TABLE se_liga_brasil.person_vote ALTER COLUMN choice DROP NOT NULL;
ALTER TABLE se_liga_brasil.person_vote ADD COLUMN IF NOT EXISTS participation_status text NOT NULL DEFAULT 'unknown';
ALTER TABLE se_liga_brasil.person_vote ADD COLUMN IF NOT EXISTS political_party_observed text;
ALTER TABLE se_liga_brasil.person_vote ADD COLUMN IF NOT EXISTS source_choice_code text;
ALTER TABLE se_liga_brasil.person_vote ADD COLUMN IF NOT EXISTS identity_method text;
UPDATE se_liga_brasil.person_vote SET participation_status=choice,choice=NULL WHERE choice IN ('absent','not_recorded');
UPDATE se_liga_brasil.person_vote SET participation_status='voted' WHERE choice IS NOT NULL AND participation_status='unknown';
CREATE INDEX IF NOT EXISTS voting_held_on_idx ON se_liga_brasil.voting(held_on DESC,id DESC);
CREATE TABLE IF NOT EXISTS se_liga_brasil.person_vote_revision (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 voting_id bigint NOT NULL REFERENCES se_liga_brasil.voting,
 person_id uuid NOT NULL REFERENCES se_liga_brasil.person,
 choice text,participation_status text NOT NULL,political_party_observed text,source_choice_code text,
 identity_method text NOT NULL,source_record_id bigint NOT NULL REFERENCES se_liga_brasil.source_record,
 valid_from timestamptz NOT NULL DEFAULT clock_timestamp(),valid_until timestamptz,
 CHECK(valid_until IS NULL OR valid_until>=valid_from)
);
CREATE UNIQUE INDEX IF NOT EXISTS person_vote_revision_current_idx ON se_liga_brasil.person_vote_revision(voting_id,person_id) WHERE valid_until IS NULL;
INSERT INTO se_liga_brasil.person_vote_revision(voting_id,person_id,choice,participation_status,
 political_party_observed,source_choice_code,identity_method,source_record_id)
SELECT voting_id,person_id,choice,participation_status,political_party_observed,source_choice_code,
 coalesce(identity_method,'legacy_observation'),source_record_id
FROM se_liga_brasil.person_vote
WHERE NOT EXISTS(SELECT 1 FROM se_liga_brasil.person_vote_revision r
 WHERE r.voting_id=person_vote.voting_id AND r.person_id=person_vote.person_id AND r.valid_until IS NULL);
CREATE INDEX IF NOT EXISTS person_vote_revision_voting_idx ON se_liga_brasil.person_vote_revision(voting_id,person_id,valid_from DESC);
CREATE INDEX IF NOT EXISTS person_vote_revision_person_idx ON se_liga_brasil.person_vote_revision(person_id,valid_from DESC);
CREATE INDEX IF NOT EXISTS person_vote_revision_source_idx ON se_liga_brasil.person_vote_revision(source_record_id);
DO $$ BEGIN
 IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conrelid='se_liga_brasil.voting'::regclass AND conname='voting_date_precision_check') THEN
  ALTER TABLE se_liga_brasil.voting ADD CONSTRAINT voting_date_precision_check CHECK(
   (date_precision='instant' AND held_at IS NOT NULL) OR (date_precision='day' AND held_on IS NOT NULL));
 END IF;
 IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conrelid='se_liga_brasil.person_vote'::regclass AND conname='person_vote_participation_check') THEN
  ALTER TABLE se_liga_brasil.person_vote ADD CONSTRAINT person_vote_participation_check CHECK(
   participation_status IN ('voted','presiding','absent','not_recorded','parliamentary_activity','excused','unknown')
   AND ((choice IS NOT NULL) = (participation_status='voted')));
 END IF;
END $$;
ALTER TABLE se_liga_brasil.person_vote_revision ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON se_liga_brasil.person_vote_revision FROM PUBLIC;
DO $$ DECLARE role_name text; BEGIN
 FOREACH role_name IN ARRAY ARRAY['anon','authenticated'] LOOP
  IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname=role_name) THEN
   EXECUTE format('REVOKE ALL ON se_liga_brasil.person_vote_revision FROM %I',role_name);
  END IF;
 END LOOP;
END $$;
COMMIT;
