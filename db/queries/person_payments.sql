WITH filters AS (
    SELECT NULL::uuid AS person_id, NULL::text AS name_query
)
SELECT
    p.id AS person_id,
    p.display_name,
    p.has_current_public_office,
    p.current_public_office_kind,
    payment.organization_code,
    payment.competence,
    payment.gross_amount,
    payment.tax_amount AS deductions_amount,
    payment.net_amount
FROM se_liga_brasil.person p
CROSS JOIN filters f
LEFT JOIN se_liga_brasil.person_payroll_payment payment
    ON payment.person_id = p.id AND payment.identity_status = 'verified'
WHERE (f.person_id IS NULL OR p.id = f.person_id)
  AND (f.name_query IS NULL OR p.display_name ILIKE '%' || f.name_query || '%')
ORDER BY p.display_name, p.id, payment.competence DESC NULLS LAST
LIMIT 200;
