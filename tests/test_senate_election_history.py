"""Election winners and their labels must not become inferred annual affiliation."""

import pytest

from crawlers.senado.election_history import parse_senate_election_history
from service.senate_history.elections import (
    attach_senate_elections,
    merge_senate_election_observations,
)

EVIDENCE = {"url": "https://www12.senado.leg.br/eleicoes", "sha256": "a" * 64}
HTML = '''<h2>1986</h2><h3>Eleita 🔄</h3>
<span style="border-radius: 999px; font-weight: 900">PMDB</span><span>100 votos</span>
<h4>Demais candidatos</h4><h3>Perdedor</h3><span>PTB</span>
<h2>1947</h2><h3>Outro eleito</h3>
<span style="border-radius: 999px; font-weight: 900">PSD/PRP/PSP</span>
<h2>1935</h2><h3>Sem legenda</h3>
<h2>Primeira República</h2><h4>1890</h4><h3>Histórico</h3>'''


def parsed():
    return parse_senate_election_history(HTML, "SP", EVIDENCE)


def test_parser_excludes_losing_candidates_and_preserves_election_year():
    rows = parsed()
    assert [row["name"] for row in rows] == ["Eleita", "Outro eleito", "Sem legenda", "Histórico"]
    assert rows[0]["political_party_literal"] == "PMDB"
    assert rows[0]["date_precision"] == "year"
    assert "observed_on" not in rows[0]
    assert rows[0]["canonical_person_id"] is None


def test_unreported_and_multiple_labels_are_not_canonical_parties():
    rows = parsed()
    assert rows[1]["political_party_interpretation"] == "multiple_labels"
    assert rows[1]["political_party_literal"] == "PSD/PRP/PSP"
    assert rows[2]["political_party_interpretation"] == "not_reported"
    assert rows[3]["election_year"] == 1890


def test_source_event_identity_is_stable_when_newer_elections_are_prepended():
    before = parsed()[0]
    after = parse_senate_election_history("<h2>2022</h2><h3>Novo</h3>" + HTML, "SP", EVIDENCE)[1]
    assert before["source_event_id"] == after["source_event_id"]


def test_election_observations_do_not_override_affiliation_total_or_roster():
    existing = [{"year": 1986, "territory_code": "SP", "institution_code": "senado",
                 "total": 3, "political_parties": [{"abbreviation": "X", "count": 3}],
                 "historical_roster": [{"name": "Arquivo"}], "members": [{"person_id": "known"}]}]
    first = merge_senate_election_observations(existing, parsed())
    repeated = merge_senate_election_observations(first, parsed())
    state = next(row for row in repeated if row["year"] == 1986 and row["territory_code"] == "SP")
    for key in ("total", "political_parties", "historical_roster", "members"):
        assert state[key] == existing[0][key]
    assert len(state["election_observations"]) == 1
    assert "election_observations" not in existing[0]
    assert len(repeated) == len(first)


def test_conflicting_source_event_id_is_rejected():
    row = parsed()[0]
    with pytest.raises(ValueError, match="SOURCE_EVENT_CONFLICT"):
        merge_senate_election_observations([], [row, {**row, "name": "Diferente"}])


def test_footer_span_cannot_become_historical_affiliation():
    rows = parse_senate_election_history(
        "<h2>1935</h2><h3>Sem legenda</h3><span>×</span><span>Fechar</span>", "SP", EVIDENCE,
    )
    assert rows[0]["political_party_literal"] is None


def test_full_history_rebuild_preserves_years_without_elections():
    existing = [{"year": 1826, "territory_code": "BR", "institution_code": "senado",
                 "historical_roster": [{"source_person_id": "1363"}]}]
    result = attach_senate_elections(existing, parsed())
    assert existing[0] in result
    assert any(row.get("election_observations") for row in result)


def test_party_badge_with_bold_nested_markup_is_read():
    rows = parse_senate_election_history(
        '<h2>1994</h2><h3>Eleito</h3><span style="background-color: #eff6ff"><b>PSDB</b></span>',
        "SP", EVIDENCE,
    )
    assert rows[0]["political_party_literal"] == "PSDB"


def test_political_label_inside_generic_election_badge_is_read_but_votes_are_not():
    rows = parse_senate_election_history(
        '<h2>2002</h2><h3>Eleita</h3><span style="border-radius: 12px; '
        'font-weight: 600; padding: 6px 12px"><b>PT</b></span><span>100 votos</span>',
        "SC", EVIDENCE,
    )
    assert rows[0]["political_party_literal"] == "PT"
