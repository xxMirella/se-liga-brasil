"""Signed source declarations must not be mistaken for malformed numeric text."""

import pytest

from crawlers.tse.normalization import normalize_asset
from normalization.scalars import normalize_money
from service.ingestion.contracts import IngestionError


@pytest.mark.parametrize("raw,expected", [("-491,27", "-491.27"), ("-1199,67", "-1199.67")])
def test_real_anonymized_negative_declarations_are_valid_signed_numbers(raw, expected):
    assert normalize_money(raw, allow_negative=True) == expected


@pytest.mark.parametrize("raw", ["--491,27", "-1.23", "-1,234", "NaN", "Infinity", "1e2"])
def test_malformed_numeric_input_stays_invalid_in_signed_mode(raw):
    with pytest.raises(IngestionError, match="INVALID_MONEY"):
        normalize_money(raw, allow_negative=True)


def test_signed_parser_retains_precision_groups_and_normalizes_negative_zero():
    assert normalize_money("-1.234,50", allow_negative=True) == "-1234.50"
    assert normalize_money("-0,00", allow_negative=True) == "0.00"
    assert normalize_money("-12.34", decimal_separator=".", allow_negative=True) == "-12.34"
    with pytest.raises(IngestionError, match="NEGATIVE_MONEY_NOT_ALLOWED"):
        normalize_money("-12,34")
    with pytest.raises(IngestionError, match="MONEY_OUT_OF_RANGE"):
        normalize_money("-1000000000000000000,00", allow_negative=True)


def test_tse_missing_values_and_valid_nonnegative_values_keep_their_contract():
    assert normalize_money("-1") is None
    with pytest.raises(IngestionError, match="REQUIRED_VALUE_MISSING"):
        normalize_money("#NULO", required=True)


@pytest.mark.parametrize("raw", ["-491,27", "-1199,67", "1234,56"])
def test_asset_preserves_source_value_and_flags_only_negative_declarations(raw):
    row = {
        "ANO_ELEICAO": "2026",
        "CD_ELEICAO": "1",
        "SQ_CANDIDATO": "123",
        "NR_ORDEM_BEM_CANDIDATO": "1",
        "CD_TIPO_BEM_CANDIDATO": "61",
        "VR_BEM_CANDIDATO": raw,
        "SG_UF": "SP",
    }
    data = normalize_asset(row)
    assert data["declaredValue"] == raw.replace(",", ".")
    if raw.startswith("-"):
        assert data["declaredValueQuality"] == "negative_requires_review"
    else:
        assert "declaredValueQuality" not in data


def test_other_sources_can_disable_tse_specific_negative_sentinels():
    assert normalize_money("-1", allow_negative=True, missing_values=frozenset({""})) == "-1.00"
    assert normalize_money("-3", allow_negative=True, missing_values=frozenset({""})) == "-3.00"
    assert normalize_money("-1", allow_negative=True) is None
