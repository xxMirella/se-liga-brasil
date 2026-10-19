BEGIN;
CREATE TABLE IF NOT EXISTS se_liga_brasil.voting_refresh_job (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 source text NOT NULL CHECK(source IN ('senado','camara')),
 requested_on date NOT NULL, starts_on date NOT NULL, ends_on date NOT NULL,
 processed boolean NOT NULL DEFAULT false,
 status text NOT NULL DEFAULT 'queued' CHECK(status IN ('queued','running','processed','failed')),
 attempts integer NOT NULL DEFAULT 0 CHECK(attempts BETWEEN 0 AND 3),
 claimed_by uuid, lease_until timestamptz, retry_after timestamptz,
 error_code text CHECK(length(error_code)<=100),
 summary jsonb NOT NULL DEFAULT '{}'::jsonb CHECK(pg_column_size(summary)<=4096),
 created_at timestamptz NOT NULL DEFAULT now(), processed_at timestamptz,
 UNIQUE(source,requested_on,starts_on), CHECK(ends_on>=starts_on),
 CHECK(processed=(status='processed'))
);
CREATE INDEX IF NOT EXISTS voting_refresh_job_pending_idx
 ON se_liga_brasil.voting_refresh_job(created_at) WHERE NOT processed;
ALTER TABLE se_liga_brasil.voting_refresh_job ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON se_liga_brasil.voting_refresh_job FROM PUBLIC;
CREATE OR REPLACE FUNCTION se_liga_brasil.enqueue_voting_refresh(
 p_requested_on date DEFAULT (now() AT TIME ZONE 'America/Belem')::date
) RETURNS integer LANGUAGE plpgsql SECURITY INVOKER
SET search_path=pg_catalog,se_liga_brasil AS $$
DECLARE inserted integer;
BEGIN
 IF p_requested_on IS NULL OR p_requested_on>(now() AT TIME ZONE 'America/Belem')::date THEN
  RAISE EXCEPTION 'INVALID_VOTING_REFRESH_DATE';
 END IF;
 INSERT INTO se_liga_brasil.voting_refresh_job(source,requested_on,starts_on,ends_on)
 SELECT source,p_requested_on,day::date,day::date
 FROM (VALUES('senado'),('camara')) sources(source)
 CROSS JOIN generate_series(p_requested_on-45,p_requested_on-1,interval '1 day') days(day)
 ON CONFLICT(source,requested_on,starts_on) DO NOTHING;
 GET DIAGNOSTICS inserted=ROW_COUNT;
 RETURN inserted;
END $$;
REVOKE ALL ON FUNCTION se_liga_brasil.enqueue_voting_refresh(date) FROM PUBLIC;
DO $$ DECLARE role_name text; BEGIN
 FOREACH role_name IN ARRAY ARRAY['anon','authenticated'] LOOP
  IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname=role_name) THEN
   EXECUTE format('REVOKE ALL ON se_liga_brasil.voting_refresh_job FROM %I',role_name);
   EXECUTE format('REVOKE ALL ON FUNCTION se_liga_brasil.enqueue_voting_refresh(date) FROM %I',role_name);
  END IF;
 END LOOP;
END $$;
COMMIT;
