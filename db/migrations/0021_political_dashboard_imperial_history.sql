-- Extend existing annual publications to the Senate's first functioning year.
DO $$
BEGIN
 IF to_regclass('se_liga_brasil.political_dashboard_annual') IS NOT NULL THEN
  ALTER TABLE se_liga_brasil.political_dashboard_annual
   DROP CONSTRAINT IF EXISTS political_dashboard_annual_year_check;
  ALTER TABLE se_liga_brasil.political_dashboard_annual
   ADD CONSTRAINT political_dashboard_annual_year_check CHECK (year BETWEEN 1826 AND 9999);
 END IF;
END
$$;
