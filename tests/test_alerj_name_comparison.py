"""ALERJ comparison ignores presentation without guessing personal identity."""

import pytest

from crawlers.alerj.pipeline import match_roster_targets, select_person_payroll
from normalization.identity import normalize_person_name
from service.ingestion.contracts import IngestionError


@pytest.mark.parametrize(
    "published_name",
    [
        "MÁRCIA HELENA SILVA JOÃO",
        "márcia helena silva joão",
        "Marcia Helena Silva Joao",
        "  Ma\u0301rcia\u00a0Helena\u2009Silva   Joa\u0303o  ",
    ],
)
def test_payroll_matches_case_accents_and_unicode_spaces(published_name):
    person = {"civil_name": "Márcia Helena Silva João"}
    row = {"recipientName": published_name}
    payroll = {normalize_person_name(published_name): row}
    assert select_person_payroll(person, payroll) is row


def test_roster_normalizes_aliases_and_deduplicates_one_person():
    person = {
        "person_id": "person-one",
        "civil_name": "Márcia Helena Silva João",
        "display_name": "Márcia João",
        "public_names": ["MARCIA JOAO", "Márcia\u00a0João"],
    }
    member = {"display_name": "  MARCIA   JOAO ", "url": "official-profile"}
    assert match_roster_targets([member], [person]) == [(person, member)]


def test_normalized_roster_homonyms_remain_unresolved():
    people = [
        {"person_id": "person-one", "civil_name": "Márcia João"},
        {"person_id": "person-two", "civil_name": "MARCIA JOAO"},
    ]
    assert match_roster_targets([{"display_name": "Marcia Joao"}], people) == []


@pytest.mark.parametrize(
    "published_name", ["MARCIA HELENA S JOAO", "MARCIA HELENA S. JOAO", "MARCIA JOAO"]
)
def test_abbreviated_payroll_names_still_require_identity_review(published_name):
    person = {"civil_name": "Márcia Helena Silva João"}
    payroll = {normalize_person_name(published_name): {"recipientName": published_name}}
    with pytest.raises(IngestionError, match="ALERJ_PAYROLL_IDENTITY_REVIEW_REQUIRED"):
        select_person_payroll(person, payroll)


def test_punctuation_does_not_silently_merge_distinct_names():
    assert normalize_person_name("Maria Ana") != normalize_person_name("Maria-Ana")
    assert normalize_person_name("Maria D'Avila") != normalize_person_name("Maria Davila")


def test_multiple_known_civil_names_with_distinct_payments_require_review():
    person = {"civil_name": "Márcia João", "civil_names": ["Márcia Silva João"]}
    payroll = {
        normalize_person_name(name): {"recipientName": name}
        for name in ["MARCIA JOAO", "MARCIA SILVA JOAO"]
    }
    with pytest.raises(IngestionError, match="ALERJ_PAYROLL_IDENTITY_REVIEW_REQUIRED"):
        select_person_payroll(person, payroll)
