-- Establish a company identity even when only its QSA or establishment is available.
INSERT INTO se_liga_brasil.business(company_base,snapshot_month,observed_on,source_record_id)
SELECT DISTINCT ON (normalized_data->>'company_base') normalized_data->>'company_base',
 (normalized_data->>'snapshot_month')::date,
 (normalized_data->>'observed_on')::date,source_record_id FROM ingestion_batch
WHERE classification NOT IN ('stale','conflicting')
ORDER BY normalized_data->>'company_base',source_generated_at DESC
ON CONFLICT(company_base) DO NOTHING;

UPDATE se_liga_brasil.business company SET
 legal_name=b.normalized_data->>'legal_name',
 legal_nature_code=b.normalized_data->>'legal_nature_code',
 share_capital=(b.normalized_data->>'share_capital')::numeric,
 size_code=b.normalized_data->>'size_code',
 snapshot_month=(b.normalized_data->>'snapshot_month')::date,
 observed_on=(b.normalized_data->>'observed_on')::date,
 source_record_id=b.source_record_id
FROM ingestion_batch b
WHERE b.normalized_data->>'fact_kind'='companies'
 AND company.company_base=b.normalized_data->>'company_base'
 AND b.classification NOT IN ('stale','conflicting')
 AND (company.snapshot_month,company.observed_on) <=
 ((b.normalized_data->>'snapshot_month')::date,(b.normalized_data->>'observed_on')::date);

INSERT INTO se_liga_brasil.business_establishment(cnpj,company_base,trade_name,
 headquarters_code,registration_status_code,registration_status_date,activity_started_on,
 primary_activity_code,uf,municipality_code,snapshot_month,observed_on,source_record_id)
SELECT normalized_data->>'cnpj',normalized_data->>'company_base',normalized_data->>'trade_name',
 normalized_data->>'headquarters_code',normalized_data->>'registration_status_code',
 (normalized_data->>'registration_status_date')::date,
 (normalized_data->>'activity_started_on')::date,normalized_data->>'primary_activity_code',
 normalized_data->>'uf',normalized_data->>'municipality_code',
 (normalized_data->>'snapshot_month')::date,
 (normalized_data->>'observed_on')::date,source_record_id FROM ingestion_batch
WHERE normalized_data->>'fact_kind'='establishments'
 AND classification NOT IN ('stale','conflicting')
ON CONFLICT(cnpj) DO UPDATE SET
 trade_name=EXCLUDED.trade_name,headquarters_code=EXCLUDED.headquarters_code,
 registration_status_code=EXCLUDED.registration_status_code,
 registration_status_date=EXCLUDED.registration_status_date,
 activity_started_on=EXCLUDED.activity_started_on,
 primary_activity_code=EXCLUDED.primary_activity_code,uf=EXCLUDED.uf,
 municipality_code=EXCLUDED.municipality_code,snapshot_month=EXCLUDED.snapshot_month,
 observed_on=EXCLUDED.observed_on,
 source_record_id=EXCLUDED.source_record_id
WHERE (se_liga_brasil.business_establishment.snapshot_month,
 se_liga_brasil.business_establishment.observed_on) <=
 (EXCLUDED.snapshot_month,EXCLUDED.observed_on);

INSERT INTO se_liga_brasil.person_business_relationship_observation(person_id,company_base,
 qualification_code,entered_on,exited_on,snapshot_month,observed_on,identity_evidence_url,
 reviewed_by,reviewed_at,source_record_id)
SELECT (normalized_data->>'person_id')::uuid,normalized_data->>'company_base',
 normalized_data->>'qualification_code',(normalized_data->>'entered_on')::date,
 NULL::date,(normalized_data->>'snapshot_month')::date,
 (normalized_data->>'observed_on')::date,normalized_data->>'identity_evidence',
 normalized_data->>'reviewed_by',(normalized_data->>'reviewed_at')::timestamptz,source_record_id
FROM ingestion_batch WHERE normalized_data->>'fact_kind'='partners'
 AND classification NOT IN ('stale','conflicting')
 AND normalized_data->>'identity_status'='reviewed'
 AND normalized_data->>'person_id' IS NOT NULL
ON CONFLICT(person_id,company_base,qualification_code,source_record_id) DO NOTHING;
