"""Reusable scalar normalization for every source adapter."""

import re
import unicodedata
from datetime import datetime, tzinfo
from typing import Any

from service.ingestion.contracts import IngestionError

MISSING_VALUES = frozenset(
    {"", "#NULO", "#NE", "-1", "-3", "-4", "NÃO DIVULGÁVEL", "NAO DIVULGAVEL"}
)


def normalize_text(
    value: Any,
    *,
    required: bool = False,
    max_length: int = 10000,
    missing_values: frozenset[str] = MISSING_VALUES,
) -> str | None:
    text = unicodedata.normalize("NFC", str("" if value is None else value)).strip()
    if text.upper() in missing_values:
        if required:
            raise IngestionError("REQUIRED_VALUE_MISSING")
        return None
    if len(text) > max_length or re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ufffd]", text):
        raise IngestionError("INVALID_TEXT")
    return text


def normalize_digits(value: Any, *, required: bool = True) -> str | None:
    text = normalize_text(value, required=required, max_length=30)
    if text is not None and not re.fullmatch(r"[0-9]+", text):
        raise IngestionError("INVALID_IDENTIFIER")
    return text


def normalize_year(value: Any, *, minimum: int = 1, maximum: int = 9999) -> int:
    year = int(normalize_digits(value))
    if not minimum <= year <= maximum:
        raise IngestionError("INVALID_YEAR")
    return year


def normalize_date(value: Any, *, date_format: str = "%d/%m/%Y") -> str | None:
    text = normalize_text(value)
    if text is None:
        return None
    try:
        parsed = datetime.strptime(text, date_format)
    except ValueError as error:
        raise IngestionError("INVALID_DATE") from error
    if parsed.strftime(date_format) != text:
        raise IngestionError("INVALID_DATE")
    return parsed.date().isoformat()


def normalize_timestamp(
    value: Any, *, time_zone: tzinfo, timestamp_format: str = "%Y-%m-%d %H:%M:%S"
) -> str | None:
    text = normalize_text(value)
    if text is None:
        return None
    try:
        parsed = datetime.strptime(text, timestamp_format)
    except ValueError as error:
        raise IngestionError("INVALID_TIMESTAMP") from error
    if parsed.strftime(timestamp_format) != text:
        raise IngestionError("INVALID_TIMESTAMP")
    return parsed.replace(tzinfo=time_zone).isoformat()


MONEY_PATTERNS = {
    ",": r"(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d{1,2})?",
    ".": r"\d+(?:\.\d{1,2})?",
}


def normalize_money(
    value: Any,
    *,
    required: bool = False,
    decimal_separator: str = ",",
    allow_negative: bool = False,
    missing_values: frozenset[str] = MISSING_VALUES,
) -> str | None:
    text = normalize_text(value, required=required, missing_values=missing_values)
    if text is None:
        return None
    is_negative = text.startswith("-")
    unsigned_text = text[1:] if is_negative else text
    pattern = MONEY_PATTERNS.get(decimal_separator)
    if pattern is None or not re.fullmatch(pattern, unsigned_text):
        raise IngestionError("INVALID_MONEY")
    if is_negative and not allow_negative:
        raise IngestionError("NEGATIVE_MONEY_NOT_ALLOWED")
    without_groups = unsigned_text.replace(".", "") if decimal_separator == "," else unsigned_text
    integer, _, fraction = without_groups.partition(decimal_separator)
    integer = integer.lstrip("0") or "0"
    if len(integer) > 18:
        raise IngestionError("MONEY_OUT_OF_RANGE")
    fraction = fraction.ljust(2, "0")
    sign = "-" if is_negative and (integer != "0" or fraction != "00") else ""
    return f"{sign}{integer}.{fraction}"


def normalize_boolean(value: Any) -> bool | None:
    text = normalize_text(value)
    if text is None:
        return None
    options = {"S": True, "SIM": True, "N": False, "NAO": False, "NÃO": False}
    if text not in options:
        raise IngestionError("INVALID_BOOLEAN")
    return options[text]
