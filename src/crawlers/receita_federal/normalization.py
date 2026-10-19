"""Keep company, establishment and QSA facts separate from personal identity."""

import re

from normalization.scalars import normalize_date, normalize_money, normalize_text
from service.ingestion.contracts import IngestionError


def normalize_company_base(value):
    if not re.fullmatch(r"[A-Z0-9]{8}", value):
        raise IngestionError("CNPJ_INVALID_COMPANY_BASE")
    return value


def normalize_cnpj_date(value):
    return None if value in {"", "00000000"} else normalize_date(value, date_format="%Y%m%d")


def normalize_company(row):
    return {
        "company_base": normalize_company_base(row[0]),
        "legal_name": normalize_text(row[1], required=True),
        "legal_nature_code": normalize_text(row[2]),
        "responsible_qualification_code": normalize_text(row[3]),
        "share_capital": normalize_money(row[4]),
        "size_code": normalize_text(row[5]),
    }


def normalize_establishment(row):
    base = normalize_company_base(row[0])
    if not re.fullmatch(r"[A-Z0-9]{4}", row[1]) or not re.fullmatch(r"[0-9]{2}", row[2]):
        raise IngestionError("CNPJ_INVALID_ESTABLISHMENT")
    return {
        "company_base": base,
        "cnpj": base + row[1] + row[2],
        "headquarters_code": row[3],
        "trade_name": normalize_text(row[4]),
        "registration_status_code": row[5],
        "registration_status_date": normalize_cnpj_date(row[6]),
        "activity_started_on": normalize_cnpj_date(row[10]),
        "primary_activity_code": row[11],
        "uf": row[19],
        "municipality_code": row[20],
    }


def normalize_partner(row):
    return {
        "company_base": normalize_company_base(row[0]),
        "partner_kind": row[1],
        "partner_name": normalize_text(row[2], required=True),
        "partner_document": normalize_text(row[3]),
        "qualification_code": row[4],
        "entered_on": normalize_cnpj_date(row[5]),
        "country_code": row[6],
        "age_range_code": row[10],
        "exited_on": None,
    }
