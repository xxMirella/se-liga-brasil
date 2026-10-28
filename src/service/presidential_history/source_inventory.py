"""Explicit collection inventory distinguishes source discovery from political coverage."""

TSE_CATALOG_URL = "https://dadosabertos.tse.jus.br/"
IBGE_HISTORY_URL = (
    "https://www.ibge.gov.br/geociencias/organizacao-do-territorio/"
    "estrutura-territorial/15771-evolucao-da-divisao-territorial-do-brasil.html"
)


def build_national_collection_inventory(territories, *, through_year):
    """One inventory row per current UF; none asserts an unverified historical government."""
    municipality_counts = {}
    for municipality in territories["municipalities"]:
        uf = municipality["uf"]
        municipality_counts[uf] = municipality_counts.get(uf, 0) + 1
    return {
        "schema_version": "political_source_inventory.v1",
        "requested_year_start": 1889, "requested_year_end": through_year,
        "territorial_catalog_observed_at": territories["observed_at"],
        "territorial_catalog_evidence": territories["evidence"],
        "territorial_history_source_url": IBGE_HISTORY_URL,
        "states": [state_collection_inventory(state, municipality_counts)
                   for state in territories["states"]],
        "limitations": [
            "current_territory_identifiers_do_not_prove_historical_existence",
            "electoral_result_does_not_prove_office_exercise_or_later_affiliation",
            "historical_territory_crosswalk_not_yet_ingested",
            "current_federal_district_not_projected_onto_old_federal_district",
        ],
    }


def state_collection_inventory(state, municipality_counts):
    uf = state["uf"]
    is_district = uf == "DF"
    return {
        "uf": uf, "ibge_code": state["ibge_code"], "name": state["name"],
        "executive_institution": "district_government" if is_district else "state_government",
        "legislative_institution": "district_chamber" if is_district else "state_assembly",
        "municipality_count_current": municipality_counts.get(uf, 0),
        "municipal_executive_applicable": not is_district,
        "municipal_legislative_applicable": not is_district,
        "historical_territory_validity": "not_yet_verified",
        "political_exercise_coverage": "not_yet_collected_by_this_inventory",
        "electoral_source_catalog_url": TSE_CATALOG_URL,
        "electoral_source_semantics": "candidacy_and_election_results_only",
        "exercise_evidence_required": ["official_possession", "official_exercise_records"],
        "political_party_evidence_required": "dated_affiliation_during_exercise",
    }
