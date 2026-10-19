import pytest

from crawlers.tse.normalization import normalize_row
from normalization.scalars import (
    normalize_boolean,
    normalize_date,
    normalize_money,
    normalize_text,
)
from service.ingestion.contracts import IngestionError, Resource


def test_non_disclosable_values_remain_unknown():
    assert normalize_boolean("Não divulgável") is None
    assert normalize_boolean("NAO DIVULGAVEL") is None
    with pytest.raises(IngestionError, match="INVALID_BOOLEAN"):
        normalize_boolean("talvez")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("1.234,56", "1234.56"), ("0,1", "0.10"), ("999999999999999999,99", "999999999999999999.99")],
)
def test_money_preserves_decimal_precision(raw, expected):
    assert normalize_money(raw) == expected


@pytest.mark.parametrize("raw", ["-4,00", "1.23", "1,234", "nan", "1000000000000000000,00"])
def test_money_rejects_invalid_values(raw):
    with pytest.raises(IngestionError):
        normalize_money(raw)


def test_invalid_date_is_rejected():
    with pytest.raises(IngestionError, match="INVALID_DATE"):
        normalize_date("31/02/2026")


def test_text_rejects_control_characters():
    with pytest.raises(IngestionError):
        normalize_text("Nome\x00inválido")


def test_content_hash_ignores_transport_timestamps_and_sensitive_identifiers(candidate_row):
    resource = Resource(
        "id", "Candidatos", "https://cdn.tse.jus.br/a.zip", "candidate", 2026, "candidatos-2026"
    )
    original = normalize_row(candidate_row, resource, entry_name="a.csv", row_number=2)
    changed = candidate_row | {"DT_GERACAO": "06/10/2026", "NR_CPF_CANDIDATO": "99999999999"}
    refreshed = normalize_row(changed, resource, entry_name="b.csv", row_number=3)
    assert original["contentSha256"] == refreshed["contentSha256"]
    assert "NR_CPF_CANDIDATO" not in str(original)
    assert original["normalizedData"]["birthDate"] == "1980-05-10"


def test_explicit_decimal_policy_accepts_dot_without_guessing():
    assert normalize_money("1270629.01", decimal_separator=".") == "1270629.01"
    with pytest.raises(IngestionError):
        normalize_money("1.234,56", decimal_separator=".")


def test_complement_timestamp_and_spending_limit_are_normalized(candidate_row):
    resource = Resource(
        "id", "Complemento", "https://cdn.tse.jus.br/a.zip", "complement", 2026, "candidatos-2026"
    )
    row = candidate_row | {
        "VR_DESPESA_MAX_CAMPANHA": "1270629.01",
        "DT_ACEITE_CANDIDATURA": "2026-08-10 10:02:25",
    }
    data = normalize_row(row, resource, entry_name="a.csv", row_number=2)["normalizedData"]
    assert data["campaignSpendingLimit"] == "1270629.01"
    assert data["candidacyAcceptedAt"] == "2026-08-10T10:02:25-03:00"
