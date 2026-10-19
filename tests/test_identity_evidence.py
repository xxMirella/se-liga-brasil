import pytest

from normalization.identity import normalize_cpf, normalize_person_name
from service.identity_resolution.evidence import IdentityEvidenceBuilder
from service.ingestion.contracts import IngestionError


def test_cpf_validates_check_digits_and_preserves_leading_digits():
    assert normalize_cpf("529.982.247-25") == "52998224725"
    assert normalize_cpf("#NULO") is None
    for invalid in ("11111111111", "52998224724", "12345", "***982247**"):
        with pytest.raises(IngestionError, match="INVALID_CPF"):
            normalize_cpf(invalid)


def test_document_fingerprint_is_stable_private_and_independent_of_party():
    builder = IdentityEvidenceBuilder(b"test-only-key-do-not-use-in-production")
    first = builder.build_evidence("João Silva", cpf="52998224725")
    second = builder.build_evidence("JOAO SILVA", cpf="529.982.247-25")
    assert first == second
    assert "52998224725" not in str(first)
    assert first["documentStatus"] == "validated"
    assert normalize_person_name("  JOÃO   Silva  ") == "joao silva"
