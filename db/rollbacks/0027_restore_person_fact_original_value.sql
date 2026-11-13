-- Rollback of 0027_person_fact_original_value_null_when_equal.sql. Idempotent.
-- PENDING: not applied.
-- Drops the trigger first (otherwise it would null the restored values again), refills
-- original_value from normalized_value where it is NULL (exactly the value it replaced, because
-- NULL only ever meant "equal"), then restores NOT NULL. Rows that diverged were never touched.
-- Refilling rewrites about 46 MB again; run it only if the semantics must be reverted.
BEGIN;
SET LOCAL lock_timeout = '10s';
DROP TRIGGER IF EXISTS person_fact_null_original_value_when_equal ON se_liga_brasil.person_fact;
DROP FUNCTION IF EXISTS se_liga_brasil.person_fact_null_original_value_when_equal();
ALTER TABLE se_liga_brasil.person_fact
  DROP CONSTRAINT IF EXISTS person_fact_original_value_null_needs_normalized_value_check;

UPDATE se_liga_brasil.person_fact SET original_value = normalized_value
WHERE id % 16 = 0 AND original_value IS NULL;
UPDATE se_liga_brasil.person_fact SET original_value = normalized_value
WHERE id % 16 = 1 AND original_value IS NULL;
UPDATE se_liga_brasil.person_fact SET original_value = normalized_value
WHERE id % 16 = 2 AND original_value IS NULL;
UPDATE se_liga_brasil.person_fact SET original_value = normalized_value
WHERE id % 16 = 3 AND original_value IS NULL;
UPDATE se_liga_brasil.person_fact SET original_value = normalized_value
WHERE id % 16 = 4 AND original_value IS NULL;
UPDATE se_liga_brasil.person_fact SET original_value = normalized_value
WHERE id % 16 = 5 AND original_value IS NULL;
UPDATE se_liga_brasil.person_fact SET original_value = normalized_value
WHERE id % 16 = 6 AND original_value IS NULL;
UPDATE se_liga_brasil.person_fact SET original_value = normalized_value
WHERE id % 16 = 7 AND original_value IS NULL;
UPDATE se_liga_brasil.person_fact SET original_value = normalized_value
WHERE id % 16 = 8 AND original_value IS NULL;
UPDATE se_liga_brasil.person_fact SET original_value = normalized_value
WHERE id % 16 = 9 AND original_value IS NULL;
UPDATE se_liga_brasil.person_fact SET original_value = normalized_value
WHERE id % 16 = 10 AND original_value IS NULL;
UPDATE se_liga_brasil.person_fact SET original_value = normalized_value
WHERE id % 16 = 11 AND original_value IS NULL;
UPDATE se_liga_brasil.person_fact SET original_value = normalized_value
WHERE id % 16 = 12 AND original_value IS NULL;
UPDATE se_liga_brasil.person_fact SET original_value = normalized_value
WHERE id % 16 = 13 AND original_value IS NULL;
UPDATE se_liga_brasil.person_fact SET original_value = normalized_value
WHERE id % 16 = 14 AND original_value IS NULL;
UPDATE se_liga_brasil.person_fact SET original_value = normalized_value
WHERE id % 16 = 15 AND original_value IS NULL;

ALTER TABLE se_liga_brasil.person_fact ALTER COLUMN original_value SET NOT NULL;
COMMIT;
