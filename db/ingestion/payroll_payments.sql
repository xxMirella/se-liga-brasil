DELETE FROM ingestion_batch WHERE classification IN ('conflicting','stale');
INSERT INTO se_liga_brasil.person_payroll_payment AS current(
 entity_id,source_id,recipient_key,recipient_name,normalized_recipient_name,person_id,identity_status,
 organization_code,office_kind,represented_uf,competence,currency,payroll_kind,
 gross_amount,tax_amount,net_amount,source_record_id,observed_at)
SELECT b.entity_id,%(source_id)s,b.normalized_data->>'recipientKey',b.normalized_data->>'recipientName',
 b.normalized_data->>'normalizedRecipientName',identity.person_id,
 CASE WHEN identity.person_id IS NULL THEN 'pending' ELSE 'verified' END,
 b.normalized_data->>'organizationCode',b.normalized_data->>'officeKind',b.normalized_data->>'representedUf',
 (b.normalized_data->>'competence')::date,b.normalized_data->>'currency',b.normalized_data->>'payrollKind',
 (b.normalized_data->>'grossAmount')::numeric,(b.normalized_data->>'taxAmount')::numeric,
 (b.normalized_data->>'netAmount')::numeric,b.source_record_id,b.source_generated_at
FROM ingestion_batch b LEFT JOIN se_liga_brasil.person_identifier identity
 ON identity.source_id=%(source_id)s AND identity.namespace='payroll_recipient'
 AND identity.external_id=b.normalized_data->>'recipientKey'
ON CONFLICT(entity_id) DO UPDATE SET
 recipient_name=excluded.recipient_name,normalized_recipient_name=excluded.normalized_recipient_name,
 gross_amount=excluded.gross_amount,tax_amount=excluded.tax_amount,net_amount=excluded.net_amount,
 source_record_id=excluded.source_record_id,observed_at=excluded.observed_at,updated_at=now(),
 person_id=coalesce(current.person_id,excluded.person_id),
 identity_status=CASE WHEN coalesce(current.person_id,excluded.person_id) IS NULL THEN 'pending' ELSE 'verified' END
WHERE excluded.observed_at>current.observed_at;
