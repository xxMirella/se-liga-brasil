"""Name compatibility needs a scoped human decision before it can link payments."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from normalization.identity import normalize_person_name
from normalization.name_variants import classify_name_variant
from service.identity_resolution.reviewed_names import reviewed_payroll_rows
from service.ingestion.contracts import IngestionError


@pytest.mark.parametrize(("registered", "published", "expected"), [
    ("Márcia Silva", "MARCIA SILVA", "normalized_exact"),
    ("Ana Gustavo Silva", "ANA G SILVA", "common_initial_abbreviation"),
    ("Ana Gustavo Silva", "ANA G. SILVA", "common_initial_abbreviation"),
    ("Ana Silva Junior", "ANA SILVA JR", "common_suffix_or_particle_variation"),
    ("Ana Silva Junior", "ANA SILVA JR.", "common_suffix_or_particle_variation"),
    ("Ana Ferreira Silva", "ANA FERREIRA DE SILVA", "common_suffix_or_particle_variation"),
    ("Ana Gustavo Silva", "ANA P SILVA", "requires_other_evidence"),
    ("Ana Gustavo Silva", "ANA SILVA", "requires_other_evidence"),
    ("Ana Silva Neto", "ANA SILVA FILHO", "requires_other_evidence"),
    ("Ana Silva", "BIA SILVA", "requires_other_evidence"),
    ("de", "da", "requires_other_evidence"),
])
def test_classification_is_not_personal_identity(registered, published, expected):
    assert classify_name_variant(registered, published) == expected


@pytest.fixture
def reviewed_case():
    person = {"person_id": str(uuid4()), "civil_name": "Ana Gustavo Silva"}
    payment = {"recipientName": "ANA G SILVA", "competence": "2026-09-01",
               "normalizedRecipientName": normalize_person_name("ANA G SILVA")}
    artifact = SimpleNamespace(sha256="a" * 64)
    review = {"decision": "approved_by_user", "source_code": "alerj",
              "person_id": person["person_id"], "registered_name": person["civil_name"],
              "published_name": payment["recipientName"], "artifact_sha256": artifact.sha256,
              "competence": payment["competence"], "review_reference": "synthetic-review-1",
              "approved_on": "2026-10-19"}
    return person, payment, artifact, review


def resolve_case(case, reviews=None, people=None):
    person, payment, artifact, review = case
    return reviewed_payroll_rows(
        [person] if people is None else people,
        {payment["normalizedRecipientName"]: payment}, artifact,
        [review] if reviews is None else reviews,
        source_code="alerj", represented_uf="RJ",
    )


def test_review_keeps_original_names_and_evidence(reviewed_case):
    person, payment, _, review = reviewed_case
    row = resolve_case(reviewed_case)[0]
    assert row["personId"] == person["person_id"]
    assert row["recipientName"] == payment["recipientName"]
    assert row["identityReview"]["review_reference"] == review["review_reference"]
    assert row["identityReview"]["classification"] == "common_initial_abbreviation"
    assert "personId" not in payment
    assert "classification" not in review
    assert resolve_case(reviewed_case, reviews=[]) == []


@pytest.mark.parametrize("field,value", [
    ("decision", "pending"), ("source_code", "other"), ("person_id", "other"),
    ("artifact_sha256", "b" * 64), ("competence", "2026-10-01"),
    ("review_reference", ""),
])
def test_approval_cannot_be_reused_for_other_scope(reviewed_case, field, value):
    reviewed_case[3][field] = value
    with pytest.raises(IngestionError):
        resolve_case(reviewed_case)


@pytest.mark.parametrize("field,value,code", [
    ("approved_on", "invalid", "REVIEWED_NAME_INVALID_APPROVAL"),
    ("registered_name", "Ana Pereira", "REVIEWED_TARGET_NAME_CHANGED"),
    ("published_name", "Ana P Silva", "REVIEWED_NAME_TARGET_NOT_FOUND"),
])
def test_changed_or_invalid_review_blocks_link(reviewed_case, field, value, code):
    reviewed_case[3][field] = value
    with pytest.raises(IngestionError, match=code):
        resolve_case(reviewed_case)


def test_duplicate_people_or_recipients_are_rejected(reviewed_case):
    review = reviewed_case[3]
    with pytest.raises(IngestionError, match="REVIEWED_NAME_LINK_AMBIGUOUS"):
        resolve_case(reviewed_case, reviews=[review, review])
    with pytest.raises(IngestionError, match="REVIEWED_NAME_TARGET_NOT_FOUND"):
        resolve_case(reviewed_case, people=[])


def test_incompatible_name_cannot_pass_as_reviewed_abbreviation(reviewed_case):
    person, _, _, review = reviewed_case
    person["civil_name"] = review["registered_name"] = "Ana Pereira Silva"
    with pytest.raises(IngestionError, match="REVIEWED_NAME_VARIANT_NOT_COMPATIBLE"):
        resolve_case(reviewed_case)


def test_recipient_payload_must_agree_with_review(reviewed_case):
    from service.identity_resolution.reviewed_names import validate_reviewed_name

    person, payment, artifact, review = reviewed_case
    payment["normalizedRecipientName"] = "another name"
    with pytest.raises(IngestionError, match="REVIEWED_PAYROLL_NAME_CHANGED"):
        validate_reviewed_name(person, payment, artifact, review, "alerj")


@pytest.mark.parametrize("failure", [None, "missing_source", "changed_review", "projection"])
def test_reviewed_collector_validates_entire_batch_before_ingestion(
    monkeypatch, tmp_path, reviewed_case, failure,
):
    from contextlib import nullcontext
    from unittest.mock import Mock

    from crawlers.alerj import reviewed_payroll as collector

    person, payment, artifact, review = reviewed_case
    repository = Mock()
    monkeypatch.setattr(collector, "IngestionRepository", lambda *_args, **_kwargs: repository)
    monkeypatch.setattr(collector.httpx, "Client", lambda **_: nullcontext(object()))
    monkeypatch.setattr(collector, "OfficialHttpClient", lambda *_: object())
    monkeypatch.setattr(collector, "AlerjAcquisition", lambda *_: object())
    document = None if failure == "missing_source" else artifact
    monkeypatch.setattr(collector, "collect_shared_evidence", lambda *_: (
        [], [], {payment["normalizedRecipientName"]: payment}, document, None,
    ))
    ingest = Mock(return_value={"new": 1})
    if failure == "changed_review":
        review["artifact_sha256"] = "b" * 64
    if failure == "projection":
        ingest.side_effect = RuntimeError("projection failure")
    monkeypatch.setattr(collector, "ingest_records", ingest)
    if failure:
        with pytest.raises((IngestionError, RuntimeError)):
            collector.collect_reviewed_payroll(object(), tmp_path, [person], [review])
        assert repository.finish_run.call_args.args[0] == "failed"
        assert ingest.call_count == int(failure == "projection")
    else:
        result = collector.collect_reviewed_payroll(object(), tmp_path, [person], [review])
        assert result["people_linked"] == 1
        assert ingest.call_count == 1
        assert repository.finish_run.call_args.args[0] == "completed"


def test_empty_review_does_not_open_database_or_network(tmp_path):
    from crawlers.alerj.reviewed_payroll import collect_reviewed_payroll

    assert collect_reviewed_payroll(None, tmp_path, [], []) == {
        "people_linked": 0, "status": "completed",
    }
