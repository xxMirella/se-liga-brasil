"""Pure normalization of names and Brazilian document identifiers."""

import re

from normalization.scalars import normalize_text
from normalization.text import fold_text
from service.ingestion.contracts import IngestionError


def normalize_person_name(value: str) -> str:
    text = normalize_text(value, required=True)
    return fold_text(text)


def normalize_cpf(value) -> str | None:
    text = normalize_text(value)
    if text is None:
        return None
    if not re.fullmatch(r"\d{11}|\d{3}\.\d{3}\.\d{3}-\d{2}", text):
        raise IngestionError("INVALID_CPF")
    digits = re.sub(r"[.-]", "", text)
    if len(set(digits)) == 1:
        raise IngestionError("INVALID_CPF")
    for length in (9, 10):
        checksum = sum(int(digits[index]) * (length + 1 - index) for index in range(length))
        check_digit = (checksum * 10 % 11) % 10
        if check_digit != int(digits[length]):
            raise IngestionError("INVALID_CPF")
    return digits
