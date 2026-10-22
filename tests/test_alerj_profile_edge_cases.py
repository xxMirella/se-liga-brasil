"""Synthetic regressions for missing ALERJ fields and explicit date evidence."""

import pytest
from test_alerj_crawler import profile_html

from crawlers.alerj.parsing import parse_profile, parse_profile_birth_date
from service.ingestion.contracts import IngestionError


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("5 de maio de 1980", "1980-05-05"),
        ("29 DE FEVEREIRO DE 2000", "2000-02-29"),
        ("5/5/1980", "1980-05-05"),
        ("5\u00a0de\u00a0março\u00a0de\u00a01980", "1980-03-05"),
    ],
)
def test_explicit_birth_formats(value, expected):
    assert parse_profile_birth_date("NASCIMENTO\n" + value) == expected


@pytest.mark.parametrize(
    "value",
    ["31 de fevereiro de 1980", "5 de inventado de 1980", "00/05/1980", "1980-05-05", ""],
)
def test_invalid_birth_is_domain_error(value):
    with pytest.raises(IngestionError, match="ALERJ_BIRTH_DATE_INVALID"):
        parse_profile_birth_date("NASCIMENTO\n" + value)


def test_unlabelled_biography_date_does_not_prove_birth():
    with pytest.raises(IngestionError, match="ALERJ_BIRTH_DATE_MISSING"):
        parse_profile_birth_date("BIOGRAFIA\n5 de maio de 1980\nCONTATO")


def test_multiple_birth_sections_are_not_silently_selected():
    with pytest.raises(IngestionError, match="ALERJ_BIRTH_DATE_AMBIGUOUS"):
        parse_profile_birth_date("NASCIMENTO\n5/5/1980\nNASCIMENTO\n6/6/1981")


@pytest.mark.parametrize(
    ("old", "new", "code"),
    [
        (b"NASCIMENTO", b"CONTATO", "ALERJ_BIRTH_DATE_MISSING"),
        (b"13\xc2\xba Legislatura", b"Mandato", "ALERJ_CURRENT_LEGISLATURE_MISSING"),
        (b"01/02/2023", b"31/02/2023", "ALERJ_AFFILIATION_DATE_INVALID"),
    ],
)
def test_profile_reports_specific_missing_or_invalid_evidence(old, new, code):
    payload = profile_html().replace(old, new)
    with pytest.raises(IngestionError) as raised:
        parse_profile(payload, "Maria Exemplo")
    assert raised.value.code == code


def test_missing_party_history_does_not_block_personal_identity_evidence():
    payload = profile_html().replace(b"Posse na ALERJ:", b"Outra observacao:")
    payload = payload.replace(b"Troca de partido: Ingresso no", b"Outra observacao:")
    profile = parse_profile(payload, "Maria Exemplo")
    assert profile["birthDate"] == "1980-05-05"
    assert profile["politicalPartyAbbreviation"] == "PSOL"
    assert profile["affiliationEvents"] == []
    assert profile["affiliationHistoryStatus"] == "not_published"
    with pytest.raises(IngestionError, match="ALERJ_BIRTH_DATE_MISSING"):
        parse_profile(payload.replace(b"NASCIMENTO", b"CONTATO"), "Maria Exemplo")


def test_name_mismatch_still_blocks_profile_with_no_birth():
    with pytest.raises(IngestionError, match="ALERJ_PROFILE_NAME_MISMATCH"):
        parse_profile(profile_html().replace(b"NASCIMENTO", b"CONTATO"), "Outra Pessoa")


@pytest.mark.parametrize(
    "code",
    [
        "ALERJ_BIRTH_DATE_MISSING",
        "ALERJ_BIRTH_DATE_INVALID",
        "ALERJ_CURRENT_LEGISLATURE_MISSING",
        "ALERJ_AFFILIATION_EVENTS_MISSING",
        "ALERJ_PAYROLL_IDENTITY_REVIEW_REQUIRED",
    ],
)
def test_target_result_preserves_specific_reason_without_ingestion(monkeypatch, code):
    from types import SimpleNamespace

    from crawlers.alerj import pipeline

    person = {"person_id": "synthetic-person"}
    monkeypatch.setattr(
        pipeline, "collect_shared_evidence", lambda *_: ([{}], [(person, {})], {}, None, None)
    )

    def fail(*_):
        raise IngestionError(code)

    monkeypatch.setattr(pipeline, "collect_verified_person", fail)
    acquisition = SimpleNamespace(configuration=SimpleNamespace(max_people=25))
    result = pipeline.collect_targets(acquisition, None, [person])
    assert result["people"] == []
    assert result["status"] == "partial"
    assert result["identity_unresolved"] == [{"person_id": "synthetic-person", "reason": code}]
