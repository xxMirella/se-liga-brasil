-- P1-A: private read-optimised serving schema. Additive and idempotent.
-- PENDING: not applied. Review, then apply with db-migrate.
-- Access model follows se_liga_brasil: RLS on, no grant to anon/authenticated. Public reads use
-- the same server-side DATABASE_URL role as the main schema, so no extra GRANT is issued.
BEGIN;
CREATE SCHEMA IF NOT EXISTS se_liga_brasil_serving;
CREATE TABLE IF NOT EXISTS se_liga_brasil_serving.dataset_release (
 name text PRIMARY KEY CHECK(name ~ '^[a-z][a-z0-9_]{0,40}$'),
 version text NOT NULL,
 built_at timestamptz NOT NULL DEFAULT now(),
 as_of date NOT NULL,
 row_count integer NOT NULL CHECK(row_count>=0)
);
ALTER TABLE se_liga_brasil_serving.dataset_release ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON SCHEMA se_liga_brasil_serving FROM PUBLIC;
REVOKE ALL ON se_liga_brasil_serving.dataset_release FROM PUBLIC;
DO $$ DECLARE role_name text; BEGIN
 FOREACH role_name IN ARRAY ARRAY['anon','authenticated'] LOOP
  IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname=role_name) THEN
   EXECUTE format('REVOKE ALL ON SCHEMA se_liga_brasil_serving FROM %I',role_name);
   EXECUTE format('REVOKE ALL ON ALL TABLES IN SCHEMA se_liga_brasil_serving FROM %I',role_name);
   EXECUTE format(
    'ALTER DEFAULT PRIVILEGES IN SCHEMA se_liga_brasil_serving REVOKE ALL ON TABLES FROM %I',
    role_name);
  END IF;
 END LOOP;
END $$;
COMMIT;
