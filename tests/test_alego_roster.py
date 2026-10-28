"""Dated official proofs, rather than seat capacity, decide the Goiás exclusions."""

from datetime import date
from pathlib import Path

import pytest

from crawlers.alego.roster import parse_directory, reconcile_current_roster
from service.ingestion.contracts import IngestionError

FIXTURES = Path(__file__).parent / "fixtures/alego"


def source_payloads():
    return [
        (FIXTURES / name).read_bytes()
        for name in [
            "directory_2026_10_27.html",
            "absences_2026_10_27.html",
            "return_2026_10_07.txt",
        ]
    ]


def test_43_directory_records_reconcile_to_41_with_documented_exclusions():
    members, excluded = reconcile_current_roster(*source_payloads(), date(2026, 10, 27))
    assert len(members) == 41
    assert {row["name"] for row in excluded} == {"Amilton Filho", "Eliel Junior"}
    assert {"Coronel Adailton", "Julio Pina", "Thiago Albernaz"}.issubset(
        {row["name"] for row in members}
    )
    assert len({row["provider_subject_id"] for row in members}) == 41


def test_seat_count_alone_cannot_justify_excluding_a_substitute():
    directory, absences, notice = source_payloads()
    absences = absences.replace(b"07/10/2026", b"07/10/2025")
    with pytest.raises(IngestionError, match="DOCUMENTED_EXCLUSION_MISSING"):
        reconcile_current_roster(directory, absences, notice, date(2026, 10, 27))


def test_older_open_titular_licences_cannot_override_the_dated_return():
    members, _ = reconcile_current_roster(*source_payloads(), date(2026, 10, 27))
    assert {"142", "145"}.issubset({row["provider_subject_id"] for row in members})


@pytest.mark.parametrize("observed_on", [date(2026, 10, 6), date(2027, 1, 1)])
def test_proof_cannot_be_applied_before_return_or_to_a_new_year(observed_on):
    with pytest.raises(IngestionError, match="PREDATES_RETURN_PROOF"):
        reconcile_current_roster(*source_payloads(), observed_on)


def test_missing_return_news_fails_instead_of_inventing_exercise():
    directory, absences, _ = source_payloads()
    with pytest.raises(IngestionError, match="TITULAR_RETURN_PROOF_MISSING"):
        reconcile_current_roster(directory, absences, b"", date(2026, 10, 27))


def test_source_directory_change_requires_new_reconciliation():
    directory = source_payloads()[0].replace(b"Eliel Junior", b"Eliel Junior</a></td></tr><tr>", 1)
    with pytest.raises(IngestionError, match="IDENTITY_OR_PARTY_MISSING"):
        parse_directory(directory)
