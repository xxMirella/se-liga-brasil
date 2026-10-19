-- Preserve rows, identifiers, references, grants and the materialized projection.
BEGIN;
SET LOCAL lock_timeout='5s';
SET LOCAL statement_timeout='30s';
ALTER TABLE se_liga_brasil.party RENAME TO political_party;
ALTER TABLE se_liga_brasil.party_affiliation RENAME TO political_party_affiliation;
ALTER TABLE se_liga_brasil.political_party_affiliation RENAME COLUMN party_id TO political_party_id;
ALTER MATERIALIZED VIEW se_liga_brasil.person_profile RENAME COLUMN last_observed_party_id TO last_observed_political_party_id;
ALTER MATERIALIZED VIEW se_liga_brasil.person_profile RENAME COLUMN last_observed_party TO last_observed_political_party;
ALTER MATERIALIZED VIEW se_liga_brasil.person_profile RENAME COLUMN party_observed_on TO political_party_observed_on;
ALTER INDEX se_liga_brasil.affiliation_latest_idx RENAME TO political_party_affiliation_latest_idx;
ALTER INDEX se_liga_brasil.person_profile_party_idx RENAME TO person_profile_political_party_idx;
-- Rename automatically named constraints, indexes and identity sequences.
DO $$
DECLARE item record; renamed text;
BEGIN
 FOR item IN SELECT c.conname,t.relname FROM pg_constraint c
 JOIN pg_class t ON t.oid=c.conrelid JOIN pg_namespace n ON n.oid=t.relnamespace
 WHERE n.nspname='se_liga_brasil' AND t.relname IN ('political_party','political_party_affiliation')
 AND c.conname LIKE 'party_%'
 LOOP
  renamed := replace(regexp_replace(item.conname,'^party','political_party'),'_party_id','_political_party_id');
  EXECUTE format('ALTER TABLE se_liga_brasil.%I RENAME CONSTRAINT %I TO %I',item.relname,item.conname,renamed);
 END LOOP;
 FOR item IN SELECT c.relname,c.relkind FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
 WHERE n.nspname='se_liga_brasil' AND c.relkind IN ('i','S') AND c.relname LIKE 'party_%'
 LOOP
  renamed := replace(regexp_replace(item.relname,'^party','political_party'),'_party_id','_political_party_id');
  IF item.relkind='i' THEN
   EXECUTE format('ALTER INDEX se_liga_brasil.%I RENAME TO %I',item.relname,renamed);
  ELSE
   EXECUTE format('ALTER SEQUENCE se_liga_brasil.%I RENAME TO %I',item.relname,renamed);
  END IF;
 END LOOP;
END $$;
COMMIT;
