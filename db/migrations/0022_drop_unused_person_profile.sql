-- P0-4: person_profile is not read by any page, query or dependent object
-- (verified via pg_depend, pg_views, pg_matviews and pg_proc). The pipelines no longer refresh it.
-- APPLIED in production on 2026-11-05; registered in apply_drop_person_profile_view.
DROP MATERIALIZED VIEW IF EXISTS se_liga_brasil.person_profile;
