"""Current affiliations and dated editorial ideology remain separate and auditable."""

import json
from pathlib import Path

from crawlers.senado.current_roster_report import parse_current_roster_report
from service.political_dashboard.orientation_composition import orientation_composition
from service.political_dashboard.orientation_timeline import orientation_cell
from service.political_dashboard.page import render_composition

ROOT = Path(__file__).resolve().parents[1]


def official_composition():
    report = json.loads((ROOT / "data/political-orientation/senate-2026-audit-20261028.json")
                        .read_text())
    return {"institution_code": "senado", "total": 81, "snapshot_on": "2026-10-28",
            "political_parties": [{"abbreviation": label, "count": count}
                                  for label, count in report["political_party_counts"].items()]}


def test_official_report_has_81_unique_members_and_three_per_uf():
    raw = ROOT / "data/political-orientation/sources/senate-current-roster-20261028.html"
    members = parse_current_roster_report(raw.read_text())
    assert len(members) == 81
    assert [(r["name"], r["uf"]) for r in members if r["political_party"] == "S/Partido"] == [
        ("ROMÁRIO", "RJ")]


def test_editorial_reference_applies_only_to_senate_in_2026():
    composition = official_composition()
    result = orientation_composition(composition, 2026)
    assert {g["orientation_category"]: g["count"] for g in result["political_parties"]} == {
        "right": 63, "left": 17, "unaffiliated": 1,
    }
    assert result["orientation_summary"]["right_excluding_disputed"] == 40
    for year, code in [(2025, "senado"), (2027, "senado"), (2026, "camara")]:
        other = orientation_composition(dict(composition, institution_code=code), year)
        assert other["orientation_summary"] is None
        assert next(g for g in other["political_parties"]
                    if g["orientation_category"] == "undetermined")["count"] == 80


def test_absolute_majority_requires_41_of_81_not_majority_of_classified():
    composition = official_composition()
    composition["political_parties"] = [
        {"abbreviation": "PL", "count": 40},
        {"abbreviation": "Partido desconhecido", "count": 41},
    ]
    result = orientation_composition(composition, 2026)
    assert not result["orientation_summary"]["has_absolute_majority"]
    assert "Sem maioria absoluta" in orientation_cell(composition, 2026, "legislative")["label"]
    composition["political_parties"][0]["count"] = 41
    composition["political_parties"][1]["count"] = 40
    assert orientation_composition(composition, 2026)["orientation_summary"][
        "has_absolute_majority"]


def test_unreconciled_party_is_not_classified_from_display_name():
    composition = official_composition()
    composition["political_parties"] = [{"abbreviation": "PL", "count": 81,
                                         "political_party_code": "unreconciled"}]
    result = orientation_composition(composition, 2026)
    assert result["political_parties"][0]["orientation_category"] == "undetermined"
    assert not result["orientation_summary"]["has_absolute_majority"]


def test_card_and_timeline_visibly_qualify_majority_and_sensitivity():
    composition = official_composition()
    cell = orientation_cell(composition, 2026, "legislative")
    assert "referência de 2022" in cell["label"]
    assert "síntese 2026" in cell["label"]
    assert "40/81" in cell["detail"] and "63/81" in cell["detail"]
    urls = {row["source_url"] for row in cell["source_evidence"]}
    assert "https://doi.org/10.7910/DVN/MFIXKW" in urls
    assert "https://psd.org.br/noticias/o-psd-na-centro-direita/" in urls
    html = render_composition(composition, "Senado Federal", "Brasil",
                              "https://www25.senado.leg.br",
                              view="political_orientation", year=2026)
    assert "Direita: 63/81 cadeiras" in html
    assert '/fontes-dos-dados#senado-2026' in html
    from service.data_sources.page import render_data_sources

    sources = render_data_sources()
    assert "direita 53/81 com MDB no centro" in sources
    assert "direita 49/81 com MDB no centro" in sources
    assert "40/81" in sources
    assert html.count("<circle ") == 81
    assert "<span>Direita</span><strong>63<small>77,8%</small></strong>" in html
    assert "Não há classificação documentada para este ano" not in html


def test_alternative_methods_keep_party_disagreements_and_same_roster():
    summary = orientation_composition(official_composition(), 2026)["orientation_summary"]
    meneguello, borges = summary["comparison_methods"]
    assert meneguello["counts"] == {
        "right": 53, "center": 10, "left": 17, "unaffiliated": 1, "undetermined": 0,
    }
    assert borges["counts"] == {
        "right": 49, "center": 14, "left": 17, "unaffiliated": 1, "undetermined": 0,
    }
    assert meneguello["has_absolute_majority"] and borges["has_absolute_majority"]
    assert summary["right_count"] == 63 and summary["right_excluding_disputed"] == 40


def test_borges_comparison_matches_original_csv_and_current_psd_identity():
    import csv

    from service.political_dashboard.senate_orientation_2026 import senate_orientation_evidence

    source = ROOT / "data/political-orientation/sources/review-psd-mdb-20261028/borges-2023.csv"
    rows = {r["party"]: r for r in csv.DictReader(source.open(), delimiter=";")
            if r["election"] == "2022"}
    assert rows["PSD"]["partycode2"] == "PSD2022"
    assert rows["PSD"]["party_facts_id"] == "4613"
    aliases = {"MDB": "PMDB", "REPUBLICANOS": "PRB", "UNIÃO": "UB"}
    method = senate_orientation_evidence()["comparison_methods"][1]
    for category in ("left", "center", "right"):
        for label in method[category]:
            assert rows[aliases.get(label, label)]["catideo3"].casefold() == category


def test_state_delegation_does_not_receive_national_majority_denominator():
    composition = {"institution_code": "senado", "territory_code": "SP", "total": 3,
                   "political_parties": [{"abbreviation": "PL", "count": 3}]}
    result = orientation_composition(composition, 2026)
    assert result["orientation_summary"] is None
    assert result["political_parties"][0]["orientation_category"] == "right"
    assert "maioria pela referência" not in orientation_cell(
        composition, 2026, "legislative")["label"]
