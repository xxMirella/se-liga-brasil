"""Validate nominal Senate payroll and reconcile monthly salary with exact decimals."""

from collections import defaultdict
from decimal import Decimal

from normalization.identity import normalize_person_name
from normalization.scalars import normalize_money
from service.ingestion.contracts import IngestionError

SALARY_COMPONENTS = (
    "remuneracao_basica",
    "vantagens_pessoais",
    "funcao_comissionada",
    "gratificacao_natalina",
    "horas_extras",
    "outras_eventuais",
    "abono_permanencia",
    "reversao_teto_constitucional",
)
DEDUCTIONS = ("imposto_renda", "previdencia", "faltas")
ALLOWANCES = ("diarias", "auxilios", "vantagens_indenizatorias")
MONEY_FIELDS = (*SALARY_COMPONENTS, *DEDUCTIONS, "remuneracao_liquida", *ALLOWANCES)


def recipient_identifier(row):
    value = row.get("sequencial")
    if type(value) is not int or value <= 0:
        raise IngestionError("SENADO_PAYROLL_RECIPIENT_ID_INVALID")
    return str(value)


def index_parliamentary_recipients(document):
    if not isinstance(document, list) or not document:
        raise IngestionError("SENADO_PARLIAMENTARY_REGISTRY_SCHEMA_CHANGED")
    names, identities = defaultdict(set), {}
    for row in document:
        if (
            not isinstance(row, dict)
            or row.get("vinculo") != "PARLAMENTAR"
            or row.get("situacao") != "ATIVO"
        ):
            raise IngestionError("SENADO_PARLIAMENTARY_REGISTRY_SCOPE_MISMATCH")
        key = recipient_identifier(row)
        name = normalize_person_name(row.get("nome"))
        if key in identities and identities[key] != name:
            raise IngestionError("SENADO_PAYROLL_RECIPIENT_CONFLICT")
        identities[key] = name
        names[name].add(key)
    return dict(names)


def index_monthly_payroll(document, period):
    if not isinstance(document, list):
        raise IngestionError("SENADO_PAYROLL_SCHEMA_CHANGED")
    indexed, names = defaultdict(list), {}
    for number, row in enumerate(document, start=1):
        if not isinstance(row, dict):
            raise IngestionError("SENADO_PAYROLL_SCHEMA_CHANGED")
        if (
            type(row.get("ano")) is not int
            or type(row.get("mes")) is not int
            or (row["ano"], row["mes"]) != (period.year, period.month)
        ):
            raise IngestionError("SENADO_PAYROLL_REFERENCE_MISMATCH")
        key = recipient_identifier(row)
        name = normalize_person_name(row.get("nome"))
        if key in names and names[key] != name:
            raise IngestionError("SENADO_PAYROLL_RECIPIENT_CONFLICT")
        names[key] = name
        indexed[key].append((number, row))
    return dict(indexed)


def normalize_payroll_entry(number, row):
    if row.get("tipo_folha") not in {"Normal", "Suplementar"}:
        raise IngestionError("SENADO_PAYROLL_KIND_NOT_SUPPORTED")
    amounts = {
        key: normalize_money(
            row.get(key), required=True, allow_negative=True, missing_values=frozenset({""})
        )
        for key in MONEY_FIELDS
    }
    gross = sum((Decimal(amounts[k]) for k in SALARY_COMPONENTS), Decimal(0))
    deductions = sum((Decimal(amounts[k]) for k in DEDUCTIONS), Decimal(0))
    if gross + deductions != Decimal(amounts["remuneracao_liquida"]):
        raise IngestionError("SENADO_PAYROLL_RECONCILIATION_FAILED")
    return {
        "rowNumber": number,
        "payrollType": row["tipo_folha"],
        "components": amounts,
        "grossAmount": str(gross + Decimal(amounts["faltas"])),
        "taxAmount": str(-Decimal(amounts["imposto_renda"]) - Decimal(amounts["previdencia"])),
        "netAmount": amounts["remuneracao_liquida"],
    }


def normalize_monthly_salary(rows, profile, recipient_key, period):
    civil_name = normalize_person_name(profile["civilName"])
    if any(normalize_person_name(row["nome"]) != civil_name for _, row in rows):
        raise IngestionError("SENADO_PAYROLL_PERSON_MISMATCH")
    entries = [normalize_payroll_entry(number, row) for number, row in rows]
    if not any(entry["payrollType"] == "Normal" for entry in entries):
        raise IngestionError("SENADO_REGULAR_PAYROLL_NOT_PUBLISHED")
    totals = {
        key: str(sum((Decimal(entry[key]) for entry in entries), Decimal(0)))
        for key in ("grossAmount", "taxAmount", "netAmount")
    }
    return {
        "personId": profile["personId"],
        "recipientKey": profile["personId"],
        "payrollRecipientSequence": recipient_key,
        "recipientName": rows[0][1]["nome"],
        "normalizedRecipientName": civil_name,
        "organizationCode": "senado",
        "officeKind": "senator",
        "representedUf": profile["representedUf"],
        "competence": period.isoformat(),
        "currency": "BRL",
        "payrollKind": "published_monthly_salary_after_mandatory_deductions",
        **totals,
        "payrollEntries": entries,
        "identityMethod": "verified_senate_profile_birth_and_unique_nominal_payroll",
        "identityEvidence": profile.get("evidence", []),
        "netScope": "salary_excludes_diarias_auxilios_and_vantagens_indenizatorias",
        "grossScope": "salary_components_after_absence_deductions",
    }
