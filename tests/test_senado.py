from crawlers.senado.normalization import normalize_profile
from crawlers.senado.pipeline import collect_senado_enrichment, index_members, select_member


def test_unsupported_fields_do_not_access_database_or_network(tmp_path):
    result = collect_senado_enrichment(None, tmp_path, [], {"current_salary"})
    assert result["unsupported_fields"] == ["current_salary"]


def test_name_only_selects_source_candidate_not_identity():
    member = {
        "IdentificacaoParlamentar": {
            "NomeCompletoParlamentar": "Pessoa Exemplo",
            "CodigoParlamentar": "1",
        }
    }
    assert select_member({"civil_name": "Pessoa Exemplo"}, index_members([member])) == member


def test_explicit_exercise_normalizes_current_office():
    profile = {
        "IdentificacaoParlamentar": {
            "NomeCompletoParlamentar": "Pessoa Exemplo",
            "UrlFotoParlamentar": "http://www.senado.leg.br/senadores/img/fotos-oficiais/senador123.jpg",
        },
        "DadosBasicosParlamentar": {"DataNascimento": "1980-01-01"},
    }
    member = {
        "Mandato": {
            "UfParlamentar": "SP",
            "DescricaoParticipacao": "Titular",
            "PrimeiraLegislaturaDoMandato": {"DataInicio": "2023-02-01", "NumeroLegislatura": "57"},
            "SegundaLegislaturaDoMandato": {"DataFim": "2031-01-31", "NumeroLegislatura": "58"},
            "Exercicios": {"Exercicio": {"DataInicio": "2023-02-01", "DataFim": "2026-10-31"}},
        }
    }
    data = normalize_profile(
        profile, member, "internal-uuid", "unique_full_name_birth_date", "2026-10-17"
    )
    assert (
        data["photoUrl"] == "https://www.senado.leg.br/senadores/img/fotos-oficiais/senador123.jpg"
    )
    assert data["inExercise"] is True
    assert data["exerciseEndExclusive"] == "2026-11-01"
    assert data["termEndExclusive"] == "2031-02-01"
    assert "CodigoParlamentar" not in data
