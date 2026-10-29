-- Rollback of db/political_dashboard_history.sql. The public application falls back to the
-- on-the-fly history query when this table is absent, so dropping it is safe at any time.
-- The annual partitions are not touched.
DROP TABLE IF EXISTS se_liga_brasil.political_dashboard_history;
