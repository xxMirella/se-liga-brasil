INSERT INTO se_liga_brasil.person_payroll_payment AS current(
 entity_id,source_id,recipient_key,recipient_name,normalized_recipient_name,person_id,identity_status,
 organization_code,office_kind,represented_uf,competence,currency,payroll_kind,
 gross_amount,tax_amount,net_amount,source_record_id,observed_at)
SELECT b.entity_id,%(source_id)s,b.normalized_data->>'recipientKey',b.normalized_data->>'recipientName',
 b.normalized_data->>'normalizedRecipientName',(b.normalized_data->>'personId')::uuid,'verified',
 'camara','federal_deputy',b.normalized_data->>'representedUf',(b.normalized_data->>'competence')::date,
 'BRL',b.normalized_data->>'payrollKind',(b.normalized_data->>'grossAmount')::numeric,
 (b.normalized_data->>'taxAmount')::numeric,(b.normalized_data->>'netAmount')::numeric,
 b.source_record_id,b.source_generated_at FROM ingestion_batch b
ON CONFLICT(entity_id) DO UPDATE SET gross_amount=excluded.gross_amount,tax_amount=excluded.tax_amount,
 net_amount=excluded.net_amount,source_record_id=excluded.source_record_id,
 observed_at=excluded.observed_at,updated_at=now()
WHERE excluded.observed_at>current.observed_at AND excluded.person_id=current.person_id;
