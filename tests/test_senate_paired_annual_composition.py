"""The two-column report must use the dated final column, never initial counts."""

import pytest

from crawlers.senado.paired_annual_composition import parse_paired_final_senate_composition

SOURCE = {"url": "https://www25.senado.leg.br/documents/report", "sha256": "b" * 64}
HEADER = "B.3 - Composições inicial e final dos Partidos Políticos e respectivas Lideranças\n"
GROUPS = {"PMDB": (20, 19), "PTB": (6, 6), "PP": (5, 5), "PT": (13, 14),
          "PDT": (4, 4), "PCdoB": (2, 2), "PSB": (4, 4), "PSDB": (11, 13),
          "PSC": (1, 1), "PV": (1, 1), "DEM": (5, 5), "PRB": (1, 1),
          "PSOL": (1, 1), "PR": (4, 3), "PSD": (1, 1), "SD": (1, 1), "PROS": (1, 0)}


def source_text():
    rows = [f"PARTIDO DOCUMENTADO - {abbreviation}\n"
            f"Em 03/02/2014: {initial} integrantes Alterações "
            f"Em 22/12/2014: {final} integrantes\n"
            for abbreviation, (initial, final) in GROUPS.items()]
    return HEADER + "".join(rows) + "B.4 - Histórico de alterações"


def test_final_column_is_selected_and_zero_final_representation_is_excluded():
    result = parse_paired_final_senate_composition(source_text(), 2014, SOURCE)
    counts = {row["abbreviation"]: row["count"] for row in result["political_parties"]}
    assert result["total"] == sum(counts.values()) == 81
    assert result["reference_on"] == "2014-12-22"
    assert counts["PMDB"] == 19 and counts["PSDB"] == 13 and counts["PT"] == 14
    assert "PROS" not in counts


def test_missing_final_column_cannot_be_replaced_with_initial_column():
    content = source_text().replace("Em 22/12/2014: 19 integrantes", "Coluna não disponível", 1)
    with pytest.raises(ValueError, match="COLUMNS_NOT_VERIFIED"):
        parse_paired_final_senate_composition(content, 2014, SOURCE)


def test_unrecognized_header_does_not_reuse_previous_political_party():
    content = source_text().replace("PARTIDO DOCUMENTADO - PTB", "Texto sem identidade partidária")
    with pytest.raises(ValueError, match="COLUMNS_NOT_VERIFIED"):
        parse_paired_final_senate_composition(content, 2014, SOURCE)
