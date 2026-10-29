"""The Itamar-period Senate keeps gaps, sensitivity and editorial caveats explicit."""

import hashlib
import json
from pathlib import Path

import pytest

from service.political_dashboard.political_orientation_catalog import classify_political_orientation
from service.political_dashboard.senate_orientation_1992_1994 import (
    SNAPSHOT_YEARS,
    category_from_score,
    party_category,
    senate_1992_1994_cell,
    senate_1992_1994_evidence,
    snapshot_summary,
    summary_text,
    year_snapshot_summary,
)
from service.political_dashboard.senate_orientation_2026 import senate_orientation_summary
from service.political_dashboard.timeline import timeline_cell


@pytest.mark.parametrize("year", SNAPSHOT_YEARS)
def test_counts_add_up_to_81_seats_with_three_per_uf(year):
    summary = year_snapshot_summary(year)
    snapshot = next(
        row
        for row in senate_1992_1994_evidence()["snapshots"]
        if row["snapshot_on"] == f"{year}-12-31"
    )
    assert summary["counted_seats"] == summary["total_seats"] == 81
    assert sum(summary["counts"].values()) == 81
    ufs = [seat["uf"] for seat in snapshot["seats"]]
    assert len(set(ufs)) == 27 and all(ufs.count(uf) == 3 for uf in set(ufs))
    occupants = [seat["occupant_source_id"] for seat in snapshot["seats"]]
    assert len(set(occupants)) == 81


@pytest.mark.parametrize("year", SNAPSHOT_YEARS)
def test_no_absolute_majority_and_gaps_are_not_centre(year):
    summary = year_snapshot_summary(year)
    assert not summary["right_has_majority"] and not summary["left_has_majority"]
    assert summary["majority_threshold"] == 41
    unresolved = (
        summary["counts"]["party_without_estimate"] + summary["counts"]["party_not_identified"]
    )
    assert unresolved == summary["unresolved_party_seats"]
    assert summary["counts"]["center"] == sum(
        1
        for seat in senate_1992_1994_evidence()["snapshots"][SNAPSHOT_YEARS.index(year)]["seats"]
        if party_category(seat["party"]["party_key"], senate_1992_1994_evidence()) == "center"
    )


def test_unknown_party_without_estimate_and_unaffiliated_are_separate_categories():
    evidence = senate_1992_1994_evidence()
    assert party_category(None, evidence) == "party_not_identified"
    assert party_category("PDC", evidence) == "party_without_estimate"
    assert party_category("S/Partido", evidence) == "unaffiliated"
    assert party_category("PMDB", evidence) == "party_without_estimate"
    assert party_category("MDB", evidence) == "center"


def test_threshold_is_proportional_to_the_project_scale_and_non_inclusive_for_extremes():
    assert [category_from_score(score, 0.1) for score in (-0.101, -0.1, 0.1, 0.101)] == [
        "left",
        "center",
        "center",
        "right",
    ]


def test_party_scores_come_from_the_1993_wave_with_explicit_identity_notes():
    evidence = senate_1992_1994_evidence()
    assert evidence["classification_source"]["wave"] == 1993
    assert evidence["parties"]["PFL"]["source_column"] == "DEM"
    assert evidence["parties"]["PDS"]["mapping_kind"] == "successor_series_inferred"
    assert evidence["parties"]["PPR"]["mapping_kind"] == "successor_series_inferred"
    assert "PDC" in evidence["unclassified_parties"]
    assert classify_political_orientation("MDB", 1993)["category"] == "undetermined"


def test_sensitivity_shows_that_mdb_position_decides_the_majority():
    for year in SNAPSHOT_YEARS:
        scenarios = {item["id"]: item for item in year_snapshot_summary(year)["sensitivity"]}
        assert scenarios["mdb_to_right"]["right_has_majority"]
        assert not scenarios["mdb_to_left"]["left_has_majority"]
        assert not scenarios["psdb_to_center"]["right_has_majority"]
        assert (
            scenarios["printed_text_claims_excluded"]["counts"]["party_not_identified"]
            > (year_snapshot_summary(year)["counts"]["party_not_identified"])
        )
    assert not {item["id"]: item for item in year_snapshot_summary(1992)["sensitivity"]}[
        "all_gaps_to_right"
    ]["right_has_majority"]


def test_text_and_cell_carry_editorial_caveats_and_sources():
    for year in SNAPSHOT_YEARS:
        summary = year_snapshot_summary(year)
        text = summary_text(summary)
        cell = senate_1992_1994_cell(year)
        assert "Síntese editorial" in text and "não relatório oficial" in text
        assert "síntese editorial" in cell["label"]
        assert cell["orientation_summary"]["evidence_kind"].startswith("editorial_application")
        assert any(
            "doi.org/10.7910/DVN/6KVTUV" in item["source_url"] for item in cell["source_evidence"]
        )


def test_timeline_uses_the_snapshot_only_for_the_senate_in_the_three_years():
    assert (
        "Sem maioria"
        in timeline_cell({"year": 1993}, "senado", "legislative", "political_orientation")["label"]
    )
    for year, code in [(1991, "senado"), (1995, "senado"), (1993, "camara")]:
        assert (
            timeline_cell({"year": year}, code, "legislative", "political_orientation")["state"]
            == "missing"
        )


def test_documented_substitutions_keep_titular_and_substitute_distinct():
    snapshot = next(
        row
        for row in senate_1992_1994_evidence()["snapshots"]
        if row["snapshot_on"] == "1992-12-31"
    )
    by_name = {seat["occupant_name"]: seat for seat in snapshot["seats"]}
    assert by_name["Eva Blay"]["occupant_role"] == "suplente_em_exercicio"
    assert "Fernando Henrique Cardoso" not in by_name
    assert by_name["Gilberto Miranda"]["party"]["party_key"] == "MDB"
    assert "Amazonino Mendes" not in by_name


def test_2026_behaviour_is_untouched():
    composition = {"institution_code": "senado", "total": 81, "political_parties": []}
    assert senate_orientation_summary(composition, 1993, {"right": 81}) is None
    assert snapshot_summary("2026-12-31") is None


EVIDENCE_FILE = Path("data/political-orientation/party-orientation-evidence-1992-1994.json")
SOURCES_DIR = Path("data/political-orientation/party-sources-1992-1994")


def test_categorical_cross_check_agrees_on_side_except_documented_personalist_party():
    evidence = senate_1992_1994_evidence()
    for key, party in evidence["parties"].items():
        check = party.get("categorical_cross_check")
        assert check, key
        if check["side"] is None:
            assert key == "PRN" and check["code"] == "P"
            continue
        assert check["side"] == party_category(key, evidence), key


def test_additional_scored_parties_and_unscored_parties_stay_separate():
    evidence = senate_1992_1994_evidence()
    assert party_category("PL", evidence) == "right"
    assert party_category("PCdoB", evidence) == "left"
    assert party_category("PPS", evidence) == "left"
    for key in ("PDC", "PSC", "PTR", "PST", "PRONA", "PSD", "PMN"):
        assert key in evidence["unclassified_parties"]
        assert party_category(key, evidence) == "party_without_estimate"
    assert "Coppedge" in evidence["unclassified_parties"]["PDC"]


def test_self_identification_never_feeds_the_score():
    evidence = senate_1992_1994_evidence()
    assert "nunca altera a pontuação" in evidence["classification_source"]["autodeclaration_policy"]
    for key in ("MDB", "PFL", "PSDB", "PDT", "PT", "PSB", "PTB", "PRN", "PDS", "PPR", "PP"):
        assert evidence["parties"][key]["self_identification_summary"]
        assert "score" in evidence["parties"][key]


def test_prn_personalist_scenario_is_reported_and_changes_no_majority_conclusion():
    for year in SNAPSHOT_YEARS:
        scenarios = {item["id"]: item for item in year_snapshot_summary(year)["sensitivity"]}
        scenario = scenarios["prn_personalist_unclassified"]
        assert scenario["counts"]["right"] < year_snapshot_summary(year)["counts"]["right"]
        assert not scenario["right_has_majority"] and not scenario["left_has_majority"]


def test_main_counts_after_party_evidence_review():
    expected = {
        1992: (31, 26, 12, 2, 3, 7),
        1993: (27, 27, 11, 3, 0, 13),
        1994: (26, 23, 13, 4, 0, 15),
    }
    for year, values in expected.items():
        counts = year_snapshot_summary(year)["counts"]
        assert tuple(
            counts[name]
            for name in (
                "right", "center", "left", "unaffiliated",
                "party_without_estimate", "party_not_identified",
            )
        ) == values


@pytest.mark.skipif(not SOURCES_DIR.exists(), reason="local data/ archive is not versioned")
def test_local_source_manifest_hashes_match_files():
    manifest = json.loads((SOURCES_DIR / "manifest.json").read_text())
    for item in manifest["sources"]:
        if item["status"] == "downloaded":
            path = Path(item["local_path"])
            assert hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"], path
        else:
            assert item["status"] == "unavailable" and item["note"]


@pytest.mark.skipif(not EVIDENCE_FILE.exists(), reason="local data/ archive is not versioned")
def test_evidence_file_keeps_self_identification_and_estimates_separate():
    records = json.loads(EVIDENCE_FILE.read_text())["parties"]
    assert {"PMDB", "PFL", "PSDB", "PDT", "PT", "PTB", "PSB", "PRN", "PDS", "PPR", "PP", "PDC"} <= {
        row["abbreviation"] for row in records
    }
    for row in records:
        assert all("estimate" not in item for item in row["self_identification"])
        assert all(item["source_id"] for item in row["expert_estimates"])
        assert row["classification_status"]
    pdc = next(r for r in records if r["abbreviation"] == "PDC")
    assert pdc["editorial_classification"]["group"] is None
