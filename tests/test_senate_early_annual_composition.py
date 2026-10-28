"""Session-final snapshots require a documented date and validated bloc member labels."""

import pytest

from crawlers.senado.early_annual_composition import parse_early_final_senate_composition

SOURCE = {"url": "https://www25.senado.leg.br/documents/report", "sha256": "c" * 64}


def source_text():
    members = "\n".join(f"Integrante {index} ({abbreviation})" for index, abbreviation in enumerate(
        ["PT"] * 7 + ["PDT"] * 3 + ["PSB"] * 3
    ))
    return '''(Período de 15.2 a 30.6 e de 1º.8 a 15.12.99)
Ao final da 1ª Sessão Legislativa Ordinária da 51ª Legislatura,
a Representação Partidária no Senado apresentava a seguinte composição:
PARTIDO DO MOVIMENTO DEMOCRÁTICO BRASILEIRO - PMDB
(26 integrantes)
PARTIDO DA FRENTE LIBERAL - PFL (21 integrantes)
PARTIDO DA SOCIAL DEMOCRACIA BRASILEIRA – PSDB (13 integrantes)
BLOCO PARLAMENTAR DE OPOSIÇÃO (13 integrantes)
''' + members + '''
PARTIDO PROGRESSISTA BRASILEIRO – PPB (02 integrantes)
PARTIDO POPULAR SOCIALISTA (3 integrantes)
PARTIDO TRABALHISTA BRASILEIRO – PTB (1 integrante)
SEM PARTIDO – 2
B.3 – Situação jurídica dos partidos'''


def test_final_ordinary_session_reference_comes_from_explicit_cover_date():
    result = parse_early_final_senate_composition(source_text(), 1999, SOURCE)
    counts = {row["abbreviation"]: row["count"] for row in result["political_parties"]}
    assert result["total"] == 81 and result["reference_on"] == "1999-12-15"
    assert counts["PMDB"] == 26 and counts["PDT"] == 3 and counts["PT"] == 7
    assert counts["PSB"] == 3 and counts["S/Partido"] == 2
    assert not any("BLOCO" in key for key in counts)
    assert "folha de rosto" in result["evidence"]["reference_date_locator"]


def test_missing_cover_date_prevents_invented_december_reference():
    with pytest.raises(ValueError, match="SESSION_END_NOT_VERIFIED"):
        parse_early_final_senate_composition(source_text().replace("a 15.12.99", ""), 1999, SOURCE)


def test_missing_bloc_member_label_prevents_claiming_complete_party_counts():
    content = source_text().replace("Integrante 0 (PT)", "Integrante sem legenda")
    with pytest.raises(ValueError, match="BLOC_MEMBER_LABEL_SUM_MISMATCH"):
        parse_early_final_senate_composition(content, 1999, SOURCE)
