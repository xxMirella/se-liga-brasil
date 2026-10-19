"""Validate ALERJ deputy payroll columns and retain exact monthly components."""

import re
import shutil
import subprocess
from datetime import date
from decimal import Decimal

from crawlers.alerj.parsing import MONTHS
from normalization.identity import normalize_person_name
from service.ingestion.contracts import IngestionError

COMPONENTS = (
    "base",
    "commission",
    "representation",
    "incorporated",
    "seniority",
    "permanence",
    "vacation",
    "ceiling_reduction",
    "ipalerj",
    "alimony",
    "social_security",
    "income_tax",
    "indemnity",
    "net",
)


def extract_pdf_text(path):
    executable = shutil.which("pdftotext")
    if executable is None:
        raise IngestionError("ALERJ_PDF_EXTRACTOR_UNAVAILABLE")
    result = subprocess.run(
        [executable, "-layout", str(path), "-"], capture_output=True, timeout=60, check=False
    )
    if result.returncode:
        raise IngestionError("ALERJ_PDF_EXTRACTION_FAILED")
    return result.stdout.decode("utf-8")


def parse_deputy_payroll(text):
    header = re.search(r"Folha de Pagamento de (\w+) de (\d{4})", text)
    if header is None:
        raise IngestionError("ALERJ_PAYROLL_COMPETENCE_MISSING")
    month, year = header.groups()
    competence = date(int(year), MONTHS[month.lower()], 1).isoformat()
    records = {}
    for line in text.splitlines():
        if "DEPUTADO ESTADUAL" not in line:
            continue
        row = normalize_deputy_row(line, competence)
        key = row["normalizedRecipientName"]
        if key in records:
            raise IngestionError("ALERJ_DUPLICATE_PAYROLL_RECIPIENT")
        records[key] = row
    if not records:
        raise IngestionError("ALERJ_NO_DEPUTY_PAYROLL_ROWS")
    return records


def normalize_deputy_row(line, competence):
    columns = re.split(r"\s{2,}", line.strip())
    if len(columns) != 16 or columns[1] != "DEPUTADO ESTADUAL":
        raise IngestionError("ALERJ_PAYROLL_COLUMN_MISMATCH")
    amounts = [parse_amount(value) for value in columns[2:]]
    gross, deductions, net = sum(amounts[:7]), sum(amounts[7:12]), amounts[13]
    if gross - deductions != net:
        raise IngestionError("ALERJ_PAYROLL_RECONCILIATION_FAILED")
    return {
        "recipientName": columns[0],
        "normalizedRecipientName": normalize_person_name(columns[0]),
        "competence": competence,
        "grossAmount": str(gross),
        "taxAmount": str(deductions),
        "netAmount": str(net),
        "payrollKind": "monthly_deputy_payroll",
        "deductionScope": "ceiling_reduction_ipalerj_alimony_social_security_income_tax",
        "indemnityIncludedInNet": False,
        "components": dict(zip(COMPONENTS, map(str, amounts), strict=True)),
    }


def parse_amount(value):
    if value == "-":
        return Decimal("0.00")
    if re.fullmatch(r"(?:\d{1,3}(?:\.\d{3})*|\d+),\d{2}", value) is None:
        raise IngestionError("ALERJ_PAYROLL_INVALID_AMOUNT")
    return Decimal(value.replace(".", "").replace(",", "."))
