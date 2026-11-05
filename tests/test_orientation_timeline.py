from service.political_dashboard.orientation_timeline import orientation_cell


def composition(**counts):
    return {"total": sum(counts.values()), "political_parties": [
        {"abbreviation": name, "count": count} for name, count in counts.items()
    ]}


def test_sums_all_parties_before_finding_largest_ideological_group():
    cell = orientation_cell(composition(PT=6, PSOL=6, PL=10), 2022, "legislative")
    assert cell["label"] == "Esquerda"
    assert "Esquerda: 12" in cell["detail"]
    assert "Direita: 10" in cell["detail"]
    assert "pluralidade não significa maioria absoluta" in cell["detail"]


def test_unclassified_members_can_prevent_established_leadership():
    cell = orientation_cell(composition(PT=10, PL=9, DESCONHECIDO=8), 2022, "legislative")
    assert "liderança incerta" in cell["label"]
    assert "Sem classificação: 8" in cell["detail"]


def test_dated_classification_does_not_fill_unobserved_historical_year():
    cell = orientation_cell(composition(PT=10, PL=9), 1966, "legislative")
    assert cell["label"] == "Sem classificação"
    assert "Sem classificação: 19" in cell["detail"]


def test_presidential_intra_year_categories_include_unaffiliated_separately():
    institution = {"segments": [{"political_party_periods": [
        {"political_party": "PT", "political_party_status": "verified_period"},
        {"political_party": "Sem partido", "political_party_status": "verified_period"},
    ]}]}
    cell = orientation_cell(institution, 2022, "executive")
    assert "Esquerda" in cell["label"]
    assert "Sem filiação" in cell["label"]
