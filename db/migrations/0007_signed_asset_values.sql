BEGIN;
SET LOCAL lock_timeout='10s';
SET LOCAL statement_timeout='120s';
ALTER TABLE se_liga_brasil.candidate_asset_declaration
 DROP CONSTRAINT candidate_asset_declaration_declared_value_check;
ALTER TABLE se_liga_brasil.candidate_asset_declaration
 ADD COLUMN value_quality_status text NOT NULL DEFAULT 'reported',
 ADD CONSTRAINT asset_value_quality_check CHECK(
  (declared_value>=0 AND value_quality_status='reported') OR
  (declared_value<0 AND value_quality_status='negative_requires_review'));
COMMENT ON COLUMN se_liga_brasil.candidate_asset_declaration.value_quality_status IS
 'Negative official declarations are preserved verbatim and require review; never converted to absolute values.';
COMMIT;
