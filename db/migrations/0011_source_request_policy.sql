BEGIN;
SET LOCAL lock_timeout='10s';
SET LOCAL statement_timeout='120s';
CREATE TABLE se_liga_brasil.source_request_policy (
 source_code text PRIMARY KEY REFERENCES se_liga_brasil.source(code),
 cooldown_until timestamptz NOT NULL DEFAULT now(),
 last_error_code text,
 last_http_status integer,
 updated_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE se_liga_brasil.source_request_policy ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON se_liga_brasil.source_request_policy FROM PUBLIC;
COMMENT ON TABLE se_liga_brasil.source_request_policy IS
 'Persistent source-wide cooldown, including gaps created after an official-source block.';
COMMIT;
