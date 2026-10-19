-- Party metadata is consolidated in political_party; source records retain provenance.
BEGIN;
SET LOCAL lock_timeout='10s';
SET LOCAL statement_timeout='30s';
DROP TABLE IF EXISTS se_liga_brasil.political_party_observation;
COMMIT;
