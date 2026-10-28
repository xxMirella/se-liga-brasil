"""Regression: the October diary supersedes an outdated 41-card web directory."""

from datetime import date
from pathlib import Path

import pytest

from crawlers.alema.diary_roster import parse_diary_roster
from service.ingestion.contracts import IngestionError
from service.state_assembly_rosters.aggregation import preserve_dated_ma_diary

FIXTURE = Path(__file__).parent / "fixtures/alema/diary_roster_2026_10_26.txt"


def test_dated_roster_includes_returned_and_substitute_members_excludes_licensed():
    roster = parse_diary_roster(FIXTURE.read_text(), date(2026, 10, 26))
    members = {row["name"]: row["political_party"] for row in roster["members"]}
    assert len(members) == 42
    assert members["Pará Figueiredo"] == "Republicanos"
    assert members["Fernando Braide"] == "PSD"
    assert "Aluízio Santos" not in members
    assert "Edson Araújo" not in members
    assert {row["name"] for row in roster["licensed"]} == {"Aluízio Santos", "Edson Araújo"}


def test_wrong_publication_date_does_not_relabel_an_old_roster():
    with pytest.raises(IngestionError, match="PUBLICATION_DATE_MISMATCH"):
        parse_diary_roster(FIXTURE.read_text(), date(2026, 10, 25))


def test_missing_member_is_rejected_rather_than_published_as_complete():
    text = FIXTURE.read_text().replace("Deputado Pará Figueiredo (Republicanos)", "")
    with pytest.raises(IngestionError, match="ROSTER_SIZE_UNEXPECTED"):
        parse_diary_roster(text, date(2026, 10, 26))


def test_committee_members_do_not_enter_the_political_roster():
    text = FIXTURE.read_text() + "\f01. Deputado Committee Only (MDB)"
    roster = parse_diary_roster(text, date(2026, 10, 26))
    assert len(roster["members"]) == 42


def test_recurring_directory_job_cannot_restore_the_obsolete_41_roster():
    old = {"territory_code": "MA", "total": 41}
    verified = {"territory_code": "MA", "total": 42, "official_roster_publication_on": "2026-10-26"}
    assert preserve_dated_ma_diary(old, [{"payload": verified}]) is verified
    complete = {"territory_code": "MA", "total": 42}
    assert preserve_dated_ma_diary(complete, [{"payload": verified}]) is complete
