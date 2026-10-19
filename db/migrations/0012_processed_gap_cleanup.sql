BEGIN;
SET LOCAL lock_timeout='10s';
SET LOCAL statement_timeout='120s';
ALTER TABLE se_liga_brasil.person_data_gap
 ADD COLUMN is_processed boolean NOT NULL DEFAULT false,
 ADD COLUMN processed_at timestamptz;
UPDATE se_liga_brasil.person_data_gap SET is_processed=true,
 processed_at=coalesce(resolved_at,last_checked_at) WHERE status='resolved';
ALTER TABLE se_liga_brasil.person_data_gap ADD CONSTRAINT gap_processed_state_check CHECK(
 (is_processed AND processed_at IS NOT NULL AND status='resolved') OR
 (NOT is_processed AND processed_at IS NULL AND status<>'resolved'));
CREATE INDEX person_data_gap_processed_idx ON se_liga_brasil.person_data_gap(id)
 WHERE is_processed;
COMMENT ON COLUMN se_liga_brasil.person_data_gap.is_processed IS
 'True only after completeness confirms resolution; failed attempts remain false and retryable.';
COMMIT;
