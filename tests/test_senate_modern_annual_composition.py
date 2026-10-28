"""Guard dated aggregate columns against party renames, footnotes and missing counts."""

import pytest

from crawlers.senado.modern_annual_composition import parse_modern_final_senate_composition

SOURCE = {"url": "https://www25.senado.leg.br/documents/report", "sha256": "d" * 64}


def report_text(first=40, second=41):
    return f'''PERÍODO DE 01/02/2019 A 23/12/2019
    B.2.1 – COMPOSIÇÃO E ALTERAÇÕES
                                      35 INTEGRANTES                  {first} INTEGRANTES
          CIDADANIA*
                                      46 INTEGRANTES                  {second} INTEGRANTES
          REPUBLICANOS***
    Alterações ocorridas
          PSD
    B.2.2 – OUTROS DADOS
'''


def test_final_counts_accept_official_footnotes_and_ignore_later_change_diagrams():
    result = parse_modern_final_senate_composition(report_text(), 2019, SOURCE)
    assert result["reference_on"] == "2019-12-23"
    counts = {row["abbreviation"]: row["count"] for row in result["political_parties"]}
    assert counts == {"CIDADANIA": 40, "REPUBLICANOS": 41}


def test_incomplete_counts_cannot_be_promoted_to_complete_81_seat_composition():
    with pytest.raises(ValueError, match="TOTAL_NOT_VERIFIED"):
        parse_modern_final_senate_composition(report_text(second=40), 2019, SOURCE)


def test_missing_final_column_does_not_reuse_initial_count():
    content = report_text().replace("46 INTEGRANTES                  41 INTEGRANTES",
                                    "46 INTEGRANTES")
    with pytest.raises(ValueError, match="INITIAL_FINAL_COUNTS_NOT_VERIFIED"):
        parse_modern_final_senate_composition(content, 2019, SOURCE)


def test_missing_cover_reference_does_not_invent_year_end_date():
    content = report_text().replace("23/12/2019", "data ausente")
    with pytest.raises(ValueError, match="SESSION_REFERENCE_NOT_VERIFIED"):
        parse_modern_final_senate_composition(content, 2019, SOURCE)


def test_explicit_no_affiliation_is_preserved_as_reported_not_unknown_or_previous_party():
    content = report_text(first=80, second=1).replace("REPUBLICANOS***", "Sem Partido")
    result = parse_modern_final_senate_composition(content, 2019, SOURCE)
    counts = {row["abbreviation"]: row["count"] for row in result["political_parties"]}
    assert counts == {"CIDADANIA": 80, "S/Partido": 1}
