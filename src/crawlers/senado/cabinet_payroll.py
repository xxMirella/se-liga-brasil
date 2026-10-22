"""Aggregate published cabinet staff payments without identifying employees by office."""

import csv
import io
import re
from collections import Counter
from decimal import Decimal

from normalization.identity import normalize_person_name
from normalization.scalars import normalize_money
from service.ingestion.contracts import IngestionError

HEADERS = (
    "VÍNCULO",
    "CATEGORIA",
    "CARGO",
    "REFERÊNCIA CARGO",
    "SÍMBOLO FUNÇÃO",
    "ANO EXERCÍCIO",
    "LOTAÇÃO EXERCÍCIO",
    "TIPO FOLHA",
    "REMUN_BASICA",
    "VANT_PESSOAIS",
    "FUNC_COMISSIONADA",
    "GRAT_NATALINA",
    "HORAS_EXTRAS",
    "OUTRAS_EVENTUAIS",
    "ABONO_PERMANENCIA",
    "REVERSAO_TETO_CONST",
    "IMPOSTO_RENDA",
    "PREVIDÊNCIA",
    "FALTAS",
    "REM_LIQUIDA",
    "DIÁRIAS",
    "AUXÍLIOS",
    "VANT_INDENIZATORIAS",
)
AMOUNT_KEYS = ("gross_amount", "allowances_amount", "total_amount")


def cabinet_name(value):
    name = normalize_person_name(value)
    match = re.fullmatch(
        r"(?:gabinete (?:do senador|da senadora)|"
        r"escritorio (?:de )?(?:apoio|ap\.)(?: (?:n[o°]?\s*)?\d+)? "
        r"(?:(?:do|da) )?(?:senador|senadora|sen\.)) (.+)",
        name,
    )
    return match[1] if match else None


def parse_payroll_rows(payload):
    rows = csv.reader(io.StringIO(payload.decode("latin1")), delimiter=";")
    update = next(rows, [])
    if len(update) != 2 or update[0] != "ÚLTIMA ATUALIZAÇÃO":
        raise IngestionError("SENADO_CABINET_PAYROLL_SCHEMA_CHANGED")
    if tuple(next(rows, [])) != HEADERS:
        raise IngestionError("SENADO_CABINET_PAYROLL_SCHEMA_CHANGED")
    for row in rows:
        if not row:
            continue
        if len(row) != len(HEADERS):
            raise IngestionError("SENADO_CABINET_PAYROLL_COLUMN_COUNT_MISMATCH")
        yield dict(zip(HEADERS, row, strict=True))


def staff_payment_amounts(row):
    amounts = [
        Decimal(
            normalize_money(
                re.sub(r"^(-?)(?=,)", r"\g<1>0", row[key]), required=True, allow_negative=True
            )
        )
        for key in HEADERS[8:]
    ]
    gross = sum(amounts[:8], Decimal(0))
    deductions = sum(amounts[8:11], Decimal(0))
    if gross + deductions != amounts[11]:
        raise IngestionError("SENADO_CABINET_PAYROLL_RECONCILIATION_FAILED")
    gross += amounts[10]  # Absence deductions reduce salary owed; tax/pension remain public cost.
    allowances = sum(amounts[12:], Decimal(0))
    return dict(zip(AMOUNT_KEYS, (gross, allowances, gross + allowances), strict=True))


def aggregate_staff_payroll(payload, period):
    if not re.fullmatch(r"20\d{2}-(?:0[1-9]|1[0-2])", period):
        raise IngestionError("INVALID_PAYROLL_MONTH")
    cabinets, skipped = {}, Counter()
    for row in parse_payroll_rows(payload):
        name = cabinet_name(row["LOTAÇÃO EXERCÍCIO"])
        if name is None:
            skipped["other_organizational_units"] += 1
            continue
        if row["VÍNCULO"] == "PARLAMENTAR" or row["CATEGORIA"] == "PARLAMENTAR":
            skipped["parliamentary_payments"] += 1
            continue
        if row["VÍNCULO"] not in {"EFETIVO", "COMISSIONADO"}:
            raise IngestionError("SENADO_CABINET_STAFF_LINK_UNSUPPORTED")
        if not row["CARGO"].strip() or not row["TIPO FOLHA"].strip():
            raise IngestionError("SENADO_CABINET_PAYROLL_ROLE_MISSING")
        amounts = staff_payment_amounts(row)
        roles = cabinets.setdefault(name, {})
        role = roles.setdefault(row["CARGO"], {key: Decimal(0) for key in AMOUNT_KEYS})
        for key in AMOUNT_KEYS:
            role[key] += amounts[key]
        role["payment_entries"] = role.get("payment_entries", 0) + 1
    if not cabinets:
        raise IngestionError("SENADO_CABINET_PAYROLL_EMPTY")
    return cabinets, dict(skipped)


def cabinet_month_record(person_id, period, roles, artifact):
    rows = [
        {
            "role": role,
            **{key: str(value) for key, value in values.items() if key in AMOUNT_KEYS},
            "payment_entries": values["payment_entries"],
        }
        for role, values in sorted(roles.items())
    ]
    totals = {
        key: str(sum((values[key] for values in roles.values()), Decimal(0))) for key in AMOUNT_KEYS
    }
    return {
        "personId": person_id,
        "period": period,
        "institution": "senado",
        "currency": "BRL",
        "roles": rows,
        **totals,
        "payment_entries": sum(r["payment_entries"] for r in rows),
        "sourceUrl": artifact.resource.url,
        "sourceSha256": artifact.sha256,
        "sourceObservedAt": artifact.fetched_at,
        "scope": "cabinet_and_support_office_staff_excludes_parliamentarian",
        "calculationVersion": 3,
    }
