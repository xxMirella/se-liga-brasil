"""Historical records keep dates, no-affiliation periods and source identity distinct."""

import json
from pathlib import Path

import pytest

from service.senate_history.affiliation_intervals import parliamentary_affiliation_intervals

ARCHIVE = Path("data/senate-history/archives/"
               "46ee6200ddeabd85ad7ccae63cbb3ca8033669aceeb73b759501664069298eb0.json")


def test_flavio_parliamentary_history_has_exclusive_boundaries_and_no_party_interval():
    records = parliamentary_affiliation_intervals(json.loads(ARCHIVE.read_text()), "5894")
    assert [(row["political_party"], row["valid_from"], row["valid_until"]) for row in records] == [
        ("PSL", "2019-01-01", "2019-11-20"),
        ("S/Partido", "2019-11-20", "2021-05-31"),
        ("PATRIOTA", "2021-05-31", "2021-11-30"),
        ("PL", "2021-11-30", None),
    ]


def test_different_official_person_identifier_is_rejected():
    with pytest.raises(ValueError, match="SENATOR_SOURCE_ID_MISMATCH"):
        parliamentary_affiliation_intervals(json.loads(ARCHIVE.read_text()), "5322")


def test_overlap_is_rejected_before_database_write():
    payload = json.loads(ARCHIVE.read_text())
    payload["FiliacaoParlamentar"]["Parlamentar"]["Filiacoes"]["Filiacao"][1][
        "DataDesfiliacao"] = "2021-11-30"
    with pytest.raises(ValueError, match="OVERLAPPING_PARLIAMENTARY_AFFILIATIONS"):
        parliamentary_affiliation_intervals(payload, "5894")
