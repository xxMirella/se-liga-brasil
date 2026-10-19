BEGIN;
SET LOCAL lock_timeout='10s';
ALTER TABLE se_liga_brasil.proposition ALTER COLUMN number DROP NOT NULL;
COMMENT ON COLUMN se_liga_brasil.proposition.number IS
 'Number explicitly published by the institution; NULL for unnumbered documents. Identity is official_key.';
COMMIT;
