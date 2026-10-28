"""Historical source precision, source-qualified identity and offline territorial contracts."""

from types import SimpleNamespace

import pytest

from crawlers.ibge.territories import (
    municipality_state,
    normalize_current_municipalities,
    normalize_current_states,
)
from crawlers.presidency.parsing import parse_first_republic_chronology
from service.ingestion.contracts import IngestionError
from service.presidential_history.biographies import (
    apply_biographical_observation,
    apply_reviewed_display_name,
    reviewed_biographical_observation,
)
from service.presidential_history.source_inventory import build_national_collection_inventory


def parse_chronology(html):
    return parse_first_republic_chronology(
        html.encode(), source_url="https://www.camara.leg.br/fixture",
        sha256="a" * 64, fetched_at="2026-10-23T00:00:00+00:00",
    )


def test_historical_year_precision_does_not_invent_dates_or_party():
    records = parse_chronology(
        "<p>1889-1891: Pessoa Histórica Um - Texto.</p>"
        "<p>1891-1894: Pessoa Histórica Dois - Foi vice-presidente em 1890.</p>"
    )
    first, second = records
    assert first["year_start"] == 1889 and first["year_end"] == 1891
    assert second["year_start"] == 1891 and second["year_end"] == 1894
    assert first["starts_on"] is None and first["ends_before"] is None
    assert first["date_precision"] == "year"
    assert first["political_party_code"] is None
    assert first["political_party_status"] == "unknown"
    assert first["canonical_person_id"] is None
    assert first["person_id"].startswith("camara-chronology:")
    assert first["evidence"][0]["sha256"] == "a" * 64


def test_chronology_excludes_executable_text_and_is_idempotent():
    html = ("<script>1889-1930: Pessoa Indevida - JS.</script>"
            "<p>1894-1898: Pessoa Histórica - Fonte.</p>")
    assert parse_chronology(html) == parse_chronology(html)
    assert len(parse_chronology(html)) == 1


@pytest.mark.parametrize("html", [
    "<p>Você não tem permissão para visualizar esta página.</p>",
    "<p>Página de acesso restrito sem cronologia.</p>",
    "<p>1888-1900: Pessoa Indevida - Não é período republicano.</p>",
    "<p>1894-1891: Pessoa Indevida - Intervalo invertido.</p>",
])
def test_invalid_or_access_denied_documents_do_not_create_governments(html):
    with pytest.raises(IngestionError):
        parse_chronology(html)


def locality(code, uf, *, modern=True):
    row = {"id": code, "nome": "Localidade de Teste"}
    if modern:
        row["regiao-imediata"] = {"regiao-intermediaria": {"UF": {"sigla": uf}}}
    else:
        row["microrregiao"] = {"mesorregiao": {"UF": {"sigla": uf}}}
    return row


def test_district_is_separate_from_municipal_government_catalog():
    states = [{"uf": "SP"}, {"uf": "DF"}]
    municipalities, districts = normalize_current_municipalities(
        [locality(3500001, "SP"), locality(5300108, "DF")], states,
    )
    assert len(municipalities) == 1 and municipalities[0]["uf"] == "SP"
    assert len(districts) == 1 and districts[0]["uf"] == "DF"
    assert "starts_on" not in municipalities[0]


def test_municipality_state_supports_new_and_legacy_ibge_regions():
    assert municipality_state(locality(3500001, "SP")) == "SP"
    assert municipality_state(locality(3500001, "SP", modern=False)) == "SP"
    with pytest.raises(IngestionError):
        municipality_state({"id": 3500001})


def test_noronha_is_a_state_district_even_in_ibge_municipality_endpoint():
    municipalities, districts = normalize_current_municipalities(
        [locality(2605459, "PE"), locality(2611606, "PE")], [{"uf": "PE"}],
    )
    assert [row["ibge_code"] for row in municipalities] == ["2611606"]
    assert [row["ibge_code"] for row in districts] == ["2605459"]


def test_municipality_catalog_rejects_duplicates_and_unknown_state():
    row = locality(3500001, "SP")
    with pytest.raises(IngestionError, match="INVALID_IDENTIFIER"):
        normalize_current_municipalities([row, row], [{"uf": "SP"}])
    with pytest.raises(IngestionError, match="STATE_UNKNOWN"):
        normalize_current_municipalities([row], [{"uf": "DF"}])


def test_partial_state_catalog_is_not_claimed_national():
    with pytest.raises(IngestionError, match="INCOMPLETE"):
        normalize_current_states([{"id": 35, "sigla": "SP", "nome": "São Paulo"}])


def test_source_inventory_does_not_claim_historical_coverage_or_district_mayors():
    catalog = {"observed_at": "2026-10-23T01:00:00+00:00", "evidence": [],
               "states": [{"ibge_code": "53", "uf": "DF", "name": "Distrito Federal"}],
               "municipalities": []}
    inventory = build_national_collection_inventory(catalog, through_year=2026)
    district = inventory["states"][0]
    assert district["municipal_executive_applicable"] is False
    assert district["historical_territory_validity"] == "not_yet_verified"
    assert district["political_exercise_coverage"] == "not_yet_collected_by_this_inventory"


def biographical_observation(kind, start=1918, end=1932):
    return {"kind": kind, "year_start": start, "year_end": end,
            "political_party_code": "historical:BR-MG:PRM",
            "political_party": "Partido Republicano Mineiro",
            "political_party_abbreviation": "PRM", "evidence": {"sha256": "a" * 64}}


def test_party_leadership_interval_supports_only_fully_covered_exercise_years():
    record = {"year_start": 1922, "year_end": 1926, "political_party_status": "unknown"}
    apply_biographical_observation(record, biographical_observation("party_leadership"))
    assert record["political_party_code"] == "historical:BR-MG:PRM"
    assert record["political_party_year_start"] == 1919
    assert record["political_party_evidence"][0]["sha256"] == "a" * 64


@pytest.mark.parametrize("kind", ["party_foundation", "presidential_election", "electoral_support"])
def test_election_support_and_foundation_do_not_become_term_affiliation(kind):
    record = {"year_start": 1922, "year_end": 1926, "political_party_status": "unknown"}
    apply_biographical_observation(record, biographical_observation(kind))
    assert record["political_party_status"] == "unknown"
    assert "political_party_code" not in record
    assert record["political_party_observations"][0]["kind"] == kind


def test_year_precision_boundary_only_verifies_interior_years():
    record = {"year_start": 1922, "year_end": 1926, "political_party_status": "unknown"}
    apply_biographical_observation(record, biographical_observation("party_leadership", 1922, 1932))
    assert record["political_party_year_start"] == 1923
    assert record["political_party_year_end"] == 1931


def test_changed_biography_claim_is_rejected_and_typo_correction_keeps_original():
    claim = {"subject": "Pessoa Histórica", "locator": "Líder do PRM (1918-1932)",
             "url": "https://www.gov.br/fixture", "record_id": "fixture"}
    artifact = SimpleNamespace(sha256="a" * 64, fetched_at="2026-10-23")
    with pytest.raises(IngestionError, match="CLAIM_CHANGED"):
        reviewed_biographical_observation(b"<h1>Outra Pessoa</h1>", claim, artifact)
    record = {"name": "Grafia Original"}
    apply_reviewed_display_name(record, {"display_name": "Grafia Verificada"}, {"url": "fonte"})
    assert record["original_source_name"] == "Grafia Original"
    assert record["name"] == "Grafia Verificada"
