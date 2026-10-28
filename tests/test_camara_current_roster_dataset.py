"""Roster membership and party evidence remain independent from cached personal biographies."""

from datetime import date
from types import SimpleNamespace

import pytest

from crawlers.camara.cached_roster import coherent_roster_observed_on
from service.political_dashboard_dataset.current_rosters import current_camara_roster_partitions


def member(code, abbreviation="AA"):
    return {
        "id": code,
        "nome": "Pessoa Fictícia " + str(code),
        "siglaUf": "SP",
        "siglaPartido": abbreviation,
    }


def identity(code):
    return {
        "person_id": "canonical-" + str(code),
        "source_record_id": str(code),
        "profile_observed_on": "2026-10-23",
        "education_level": "Fictional",
        "political_party_abbreviation": "BIOGRAPHY_PARTY",
    }


def test_common_roster_dates_and_party_do_not_rewrite_personal_profile_evidence():
    partitions = current_camara_roster_partitions(
        [member(1)], [], {"1": identity(1)}, date(2026, 10, 22)
    )
    national = next(item for item in partitions if item["territory_code"] == "BR")
    assert national["snapshot_on"] == "2026-10-22"
    assert national["political_parties"][0]["abbreviation"] == "AA"
    assert national["members"][0]["capacity"] is None
    assert "education_level" not in national["members"][0]
    assert national["canonical_roster_matches"] == 1
    assert national["coverage"] == "verified_current_roster"


def test_unmatched_roster_people_do_not_receive_an_arbitrary_canonical_identity():
    partitions = current_camara_roster_partitions(
        [member(1), member(2)], [], {"1": identity(1)}, date(2026, 10, 22)
    )
    national = next(item for item in partitions if item["territory_code"] == "BR")
    assert national["total"] == 1 and national["official_roster_size"] == 2
    assert national["coverage"] == "observed_partial"


def test_roster_pages_with_different_dates_do_not_claim_a_common_snapshot():
    artifacts = [
        SimpleNamespace(fetched_at="2026-10-22T18:00:00+00:00"),
        SimpleNamespace(fetched_at="2026-10-23T18:00:00+00:00"),
    ]
    assert coherent_roster_observed_on(artifacts) is None


def test_repeated_official_identifiers_abort_the_snapshot():
    with pytest.raises(ValueError, match="DUPLICATE_PROVIDER"):
        current_camara_roster_partitions(
            [member(1), member(1)], [], {"1": identity(1)}, date(2026, 10, 22)
        )
