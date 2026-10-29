-- Private publication table: the reduced yearly history of one territory, built once when the
-- annual partitions are published and read by primary key on public requests.
-- Payload is canonical JSON (political_dashboard_history.v1) compressed with zlib: the
-- timeline of a territory is read on every cold request, so wire size is what matters.
CREATE TABLE IF NOT EXISTS se_liga_brasil.political_dashboard_history (
 territory_code text PRIMARY KEY CHECK (territory_code ~ '^(BR|[A-Z]{2}|[0-9]{7})$'),
 schema_version text NOT NULL CHECK (schema_version ~ '^political_dashboard_history\.v[0-9]+$'),
 content_sha256 text NOT NULL CHECK (content_sha256 ~ '^[a-f0-9]{64}$'),
 row_count integer NOT NULL CHECK (row_count >= 0),
 uncompressed_bytes integer NOT NULL CHECK (uncompressed_bytes BETWEEN 2 AND 16777216),
 payload_zlib bytea NOT NULL CHECK (octet_length(payload_zlib) BETWEEN 1 AND 4194304),
 published_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE se_liga_brasil.political_dashboard_history ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON se_liga_brasil.political_dashboard_history FROM anon, authenticated;
