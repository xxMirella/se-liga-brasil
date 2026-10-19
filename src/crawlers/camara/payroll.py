"""Exact published salary reconciliation; allowances remain separate components."""

import re
from decimal import Decimal

from normalization.identity import normalize_person_name
from normalization.scalars import normalize_money
from normalization.text import fold_text
from parsing.html import HtmlTableParser, decode_html
from service.ingestion.contracts import IngestionError
from storage.files import hash_content


def published_salary_months(payload: bytes) -> list[str]:
    text = decode_html(payload)
    matches = re.findall(r"mesAno=(\d{2})(\d{4})", text)
    return sorted({f"{year}-{month}" for month, year in matches})


def parse_salary_components(payload, competence, display_name) -> dict:
    parser = HtmlTableParser(None)
    parser.feed(decode_html(payload))
    text = " ".join(parser.text)
    year, month = competence.split("-")
    if not re.search(rf"\b{month}/{year}\s*-\s*FOLHA NORMAL\b", text):
        raise IngestionError("CAMARA_PAYROLL_REFERENCE_MISMATCH")
    if normalize_person_name(display_name) not in fold_text(" ".join(text.split())):
        raise IngestionError("CAMARA_PAYROLL_PERSON_MISMATCH")
    return parse_component_rows(parser.rows)


def parse_component_rows(rows) -> dict:
    section, components = None, {}
    for cells in rows:
        if len(cells) == 1 and re.match(r"^[1-6] - ", cells[0]):
            section = cells[0][0]
            continue
        if not section or len(cells) != 2 or not re.match(r"^[a-z] - ", cells[0]):
            continue
        key = section + ":" + cells[0]
        if key in components:
            raise IngestionError("CAMARA_DUPLICATE_PAYROLL_COMPONENT")
        components[key] = normalize_money(cells[1], required=True, allow_negative=True)
    if not {"1", "4", "5"}.issubset({key[0] for key in components}):
        raise IngestionError("CAMARA_PAYROLL_SCHEMA_CHANGED")
    return components


def normalize_salary(payload, competence, profile) -> dict:
    components = parse_salary_components(payload, competence, profile["displayName"])
    gross = sum((Decimal(v) for k, v in components.items() if k[0] in "123"), Decimal(0))
    discounts = sum((Decimal(v) for k, v in components.items() if k[0] == "4"), Decimal(0))
    net_values = [Decimal(v) for k, v in components.items() if k[0] == "5"]
    if len(net_values) != 1 or discounts > 0 or gross + discounts != net_values[0]:
        raise IngestionError("CAMARA_PAYROLL_RECONCILIATION_FAILED")
    return {
        "personId": profile["personId"],
        "recipientName": profile["displayName"],
        "recipientKey": hash_content(profile["personId"]),
        "normalizedRecipientName": normalize_person_name(profile["displayName"]),
        "competence": competence + "-01",
        "organizationCode": "camara",
        "officeKind": "federal_deputy",
        "representedUf": profile["representedUf"],
        "currency": "BRL",
        "payrollKind": "salary_after_mandatory_deductions",
        "grossAmount": f"{gross:.2f}",
        "taxAmount": f"{-discounts:.2f}",
        "netAmount": f"{net_values[0]:.2f}",
        "components": components,
        "deductionScope": "mandatory_deductions_including_tax_and_pension_contribution",
        "netScope": "published_salary_after_mandatory_deductions_excludes_section_6_allowances",
    }
