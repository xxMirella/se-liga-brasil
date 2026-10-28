-- Private publication table: one content-addressed annual projection per selected scope.
CREATE TABLE IF NOT EXISTS se_liga_brasil.political_dashboard_annual (
 year integer NOT NULL CHECK (year BETWEEN 1826 AND 9999),
 territory_code text NOT NULL CHECK (territory_code ~ '^(BR|[A-Z]{2}|[0-9]{7})$'),
 institution_code text NOT NULL,
 content_sha256 text NOT NULL CHECK (content_sha256 ~ '^[a-f0-9]{64}$'),
 payload jsonb NOT NULL CHECK (jsonb_typeof(payload)='object'),
 published_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY (year, territory_code, institution_code)
);
ALTER TABLE se_liga_brasil.political_dashboard_annual ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON se_liga_brasil.political_dashboard_annual FROM anon, authenticated;
CREATE INDEX IF NOT EXISTS political_dashboard_annual_territory_year_idx
 ON se_liga_brasil.political_dashboard_annual (territory_code, year);

CREATE TABLE IF NOT EXISTS se_liga_brasil.political_dashboard_territory_catalog (
 territory_code text PRIMARY KEY CHECK (territory_code ~ '^[A-Z]{2}$'),
 content_sha256 text NOT NULL CHECK (content_sha256 ~ '^[a-f0-9]{64}$'),
 payload jsonb NOT NULL CHECK (jsonb_typeof(payload)='object'),
 published_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE se_liga_brasil.political_dashboard_territory_catalog ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON se_liga_brasil.political_dashboard_territory_catalog FROM anon, authenticated;
