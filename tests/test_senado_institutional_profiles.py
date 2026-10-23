"""Institutional identities require personal evidence, never electoral participation."""

from copy import deepcopy

import pytest

from crawlers.senado.institutional_profile import normalize_institutional_profile
from crawlers.senado.roster_collection import acquire_national_roster_batch
from service.ingestion.contracts import IngestionError


@pytest.fixture
def institutional_subject():
    identification = {
        "CodigoParlamentar": "123456",
        "NomeCompletoParlamentar": "Pessoa Civil Fictícia",
        "NomeParlamentar": "Pessoa Pública",
        "SiglaPartidoParlamentar": "TESTE",
    }
    profile = {
        "DetalheParlamentar": {
            "Parlamentar": {
                "IdentificacaoParlamentar": identification,
                "DadosBasicosParlamentar": {"DataNascimento": "1980-01-01"},
            }
        }
    }
    member = {
        "IdentificacaoParlamentar": deepcopy(identification),
        "Mandato": {
            "UfParlamentar": "AC",
            "DescricaoParticipacao": "1º Suplente",
            "PrimeiraLegislaturaDoMandato": {"DataInicio": "2023-02-01", "NumeroLegislatura": "57"},
            "SegundaLegislaturaDoMandato": {"DataFim": "2031-01-31", "NumeroLegislatura": "58"},
            "Exercicios": {"Exercicio": {"DataInicio": "2026-08-01"}},
        },
    }
    return profile, member


def test_national_profile_preserves_civil_public_names_and_substitute_exercise(
    institutional_subject,
):
    data = normalize_institutional_profile(*institutional_subject, "2026-10-22")
    assert data["civilName"] == "Pessoa Civil Fictícia"
    assert data["displayName"] == "Pessoa Pública"
    assert data["personId"] is None
    assert data["capacity"] == "substitute"
    assert data["exerciseStartsOn"] == "2026-08-01"
    assert data["termStart"] == "2023-02-01"


@pytest.mark.parametrize("birth", [None, "", "not-a-date", "2030-01-01"])
def test_missing_invalid_or_future_birth_requires_review(institutional_subject, birth):
    profile, member = institutional_subject
    profile["DetalheParlamentar"]["Parlamentar"]["DadosBasicosParlamentar"]["DataNascimento"] = (
        birth
    )
    with pytest.raises(IngestionError, match="SENATE_INSTITUTIONAL_IDENTITY_INSUFFICIENT"):
        normalize_institutional_profile(profile, member, "2026-10-22")


def test_roster_and_profile_keys_must_agree(institutional_subject):
    profile, member = institutional_subject
    member["IdentificacaoParlamentar"]["CodigoParlamentar"] = "987654"
    with pytest.raises(IngestionError, match="SENATE_IDENTITY_PROFILE_KEY_MISMATCH"):
        normalize_institutional_profile(profile, member, "2026-10-22")


@pytest.mark.parametrize("limit,offset", [(0, 0), (26, 0), (10, -1), (True, 0)])
def test_invalid_roster_batch_never_accesses_database_or_network(limit, offset, tmp_path):
    with pytest.raises(IngestionError, match="INVALID_SENATE_ROSTER_BATCH"):
        acquire_national_roster_batch(None, tmp_path, limit=limit, offset=offset)
