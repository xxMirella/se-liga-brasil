"""Pure normalization of the published monthly deputy payroll aggregate."""

from decimal import Decimal

from normalization.identity import normalize_person_name
from normalization.scalars import normalize_money, normalize_text
from service.ingestion.contracts import IngestionError
from storage.files import hash_content


def normalize_payroll_row(cells: list[str], competence: str) -> dict:
    if len(cells) != 4:
        raise IngestionError("PAYROLL_COLUMN_COUNT_MISMATCH")
    name = normalize_text(cells[0], required=True, max_length=300)
    amounts = [
        normalize_money(value, required=True, allow_negative=True, missing_values=frozenset({""}))
        for value in cells[1:]
    ]
    gross, taxes, net = map(Decimal, amounts)
    if gross - taxes != net:
        raise IngestionError("PAYROLL_AMOUNT_RECONCILIATION_FAILED")
    normalized_name = normalize_person_name(name)
    return {
        "recipientName": name,
        "normalizedRecipientName": normalized_name,
        "recipientKey": hash_content(normalized_name),
        "competence": f"{competence}-01",
        "officeKind": "state_deputy",
        "organizationCode": "alesp",
        "representedUf": "SP",
        "currency": "BRL",
        "grossAmount": amounts[0],
        "taxAmount": amounts[1],
        "netAmount": amounts[2],
        "payrollKind": "published_monthly_aggregate",
        "timestampBasis": "collected_at",
        "identityBasis": "published_name_only",
    }
