-- Some official parliamentary documents have no numbered year (API reports zero).
BEGIN;
SET LOCAL lock_timeout='10s';
SET LOCAL statement_timeout='120s';
ALTER TABLE se_liga_brasil.proposition ALTER COLUMN year DROP NOT NULL;
COMMENT ON COLUMN se_liga_brasil.proposition.year IS
 'Official numbered year when known; source zero/absence is normalized to NULL, never inferred.';
COMMIT;
