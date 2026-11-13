-- Storage (R3): person_fact.original_value stores NULL when it equals normalized_value.
-- PENDING: not applied. Not wired to db-migrate or operations.py. Idempotent; rollback in
-- db/rollbacks/0027_restore_person_fact_original_value.sql.
--
-- New meaning (see docs/modelo-de-dados.md): original_value IS NULL  <=>  "identical to
-- normalized_value". Every row where the two values differ keeps its original_value untouched, so
-- no divergent source data is lost. The effective value is coalesce(original_value, normalized_value);
-- no reader in src/, db/, scripts/ or app.py reads original_value today (audited 2026-11-12).
--
-- Mechanism: (1) DROP NOT NULL, (2) a BEFORE INSERT/UPDATE trigger nulls the column when equal, so
-- the ~20 INSERTs (db/ingestion/*.sql, src/database/*.py, scripts/reconcile_alesp_exercise.py)
-- keep writing the raw value and stay unchanged, (3) a CHECK stops a NULL original with a NULL
-- normalized_value (that would mean "equal to nothing"), (4) the existing rows are rewritten in 16
-- separate statements (id % 16) so each one stays far below statement_timeout.
--
-- Space: UPDATE only creates dead tuples. The ~46 MB returns to the operating system only after
-- a table rewrite (pg_repack or VACUUM FULL, outside this migration; see
-- scripts/maintenance_reclaim_table_bloat.py). autovacuum alone lets later writes reuse the pages.
-- Locks: short ACCESS EXCLUSIVE for ALTER/CREATE TRIGGER (lock_timeout 10s); run outside a
-- collection run. The 16 UPDATEs take only row locks.
BEGIN;
SET LOCAL lock_timeout = '10s';
ALTER TABLE se_liga_brasil.person_fact ALTER COLUMN original_value DROP NOT NULL;

CREATE OR REPLACE FUNCTION se_liga_brasil.person_fact_null_original_value_when_equal()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'UPDATE' AND NEW.original_value IS NULL AND OLD.original_value IS NULL
     AND NEW.normalized_value IS DISTINCT FROM OLD.normalized_value THEN
    -- NULL meant "equal to the old normalized value"; keep that fact before it is overwritten.
    NEW.original_value := OLD.normalized_value;
  END IF;
  IF NEW.original_value IS NOT NULL AND NEW.original_value = NEW.normalized_value THEN
    NEW.original_value := NULL;
  END IF;
  RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS person_fact_null_original_value_when_equal ON se_liga_brasil.person_fact;
CREATE TRIGGER person_fact_null_original_value_when_equal
BEFORE INSERT OR UPDATE OF original_value, normalized_value ON se_liga_brasil.person_fact
FOR EACH ROW EXECUTE FUNCTION se_liga_brasil.person_fact_null_original_value_when_equal();

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint
                 WHERE conrelid = 'se_liga_brasil.person_fact'::regclass
                   AND conname = 'person_fact_original_value_null_needs_normalized_value_check') THEN
    ALTER TABLE se_liga_brasil.person_fact
      ADD CONSTRAINT person_fact_original_value_null_needs_normalized_value_check
      CHECK (original_value IS NOT NULL OR normalized_value IS NOT NULL) NOT VALID;
  END IF;
END
$$;

UPDATE se_liga_brasil.person_fact SET original_value = NULL
WHERE id % 16 = 0 AND original_value IS NOT NULL AND original_value = normalized_value;
UPDATE se_liga_brasil.person_fact SET original_value = NULL
WHERE id % 16 = 1 AND original_value IS NOT NULL AND original_value = normalized_value;
UPDATE se_liga_brasil.person_fact SET original_value = NULL
WHERE id % 16 = 2 AND original_value IS NOT NULL AND original_value = normalized_value;
UPDATE se_liga_brasil.person_fact SET original_value = NULL
WHERE id % 16 = 3 AND original_value IS NOT NULL AND original_value = normalized_value;
UPDATE se_liga_brasil.person_fact SET original_value = NULL
WHERE id % 16 = 4 AND original_value IS NOT NULL AND original_value = normalized_value;
UPDATE se_liga_brasil.person_fact SET original_value = NULL
WHERE id % 16 = 5 AND original_value IS NOT NULL AND original_value = normalized_value;
UPDATE se_liga_brasil.person_fact SET original_value = NULL
WHERE id % 16 = 6 AND original_value IS NOT NULL AND original_value = normalized_value;
UPDATE se_liga_brasil.person_fact SET original_value = NULL
WHERE id % 16 = 7 AND original_value IS NOT NULL AND original_value = normalized_value;
UPDATE se_liga_brasil.person_fact SET original_value = NULL
WHERE id % 16 = 8 AND original_value IS NOT NULL AND original_value = normalized_value;
UPDATE se_liga_brasil.person_fact SET original_value = NULL
WHERE id % 16 = 9 AND original_value IS NOT NULL AND original_value = normalized_value;
UPDATE se_liga_brasil.person_fact SET original_value = NULL
WHERE id % 16 = 10 AND original_value IS NOT NULL AND original_value = normalized_value;
UPDATE se_liga_brasil.person_fact SET original_value = NULL
WHERE id % 16 = 11 AND original_value IS NOT NULL AND original_value = normalized_value;
UPDATE se_liga_brasil.person_fact SET original_value = NULL
WHERE id % 16 = 12 AND original_value IS NOT NULL AND original_value = normalized_value;
UPDATE se_liga_brasil.person_fact SET original_value = NULL
WHERE id % 16 = 13 AND original_value IS NOT NULL AND original_value = normalized_value;
UPDATE se_liga_brasil.person_fact SET original_value = NULL
WHERE id % 16 = 14 AND original_value IS NOT NULL AND original_value = normalized_value;
UPDATE se_liga_brasil.person_fact SET original_value = NULL
WHERE id % 16 = 15 AND original_value IS NOT NULL AND original_value = normalized_value;

ALTER TABLE se_liga_brasil.person_fact
  VALIDATE CONSTRAINT person_fact_original_value_null_needs_normalized_value_check;
COMMIT;
