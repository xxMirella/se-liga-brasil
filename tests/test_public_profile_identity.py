"""Identity block, summary cards and section navigation of the single-page profile."""

from service.public_profile_web.profile import render_profile_header, title_case_name
from service.public_profile_web.profile_dates import format_full_date, format_reais
from service.public_profile_web.profile_navigation import (
    PROFILE_SECTIONS,
    render_section_navigation,
)
from service.public_profile_web.profile_summary import render_profile_summary

PROFILE = {
    "display_name": "ERIKA DE <b>HILTON</b>",
    "photo": {"url": "https://www.camara.leg.br/internet/deputado/bandep/220645.jpg"},
    "age": {"value": 33},
    "education_level": "SUPERIOR COMPLETO",
    "political_party": {"abbreviation": "PSOL", "name": "PARTIDO SOCIALISMO E LIBERDADE"},
    "current_offices": [{
        "office_kind": "federal_deputy", "represented_uf": "SP", "capacity": "holder",
        "institution": {"name": "Câmara dos Deputados"}, "starts_on": "2023-02-01",
        "remaining_term": {"status": "documented_term_boundary", "last_day": "2027-01-31"},
    }],
}


def test_identity_follows_reference_text():
    html = render_profile_header(PROFILE)
    assert "Perfil público" in html
    assert "Deputado(a) federal por São Paulo" in html
    assert "<strong>PSOL</strong>" in html
    assert "(Partido Socialismo e Liberdade)" in html
    assert "Em exercício desde fev/2023" in html
    assert "Mandato termina em 31/01/2027" in html
    assert "33 anos · superior completo" in html


def test_identity_escapes_names_and_rejects_unofficial_photo():
    html = render_profile_header(PROFILE | {"photo": {"url": "http://evil.example/a.jpg"}})
    assert "<b>" not in html
    assert "evil.example" not in html
    assert "Foto não disponível" in html


def test_identity_without_data_never_invents_values():
    html = render_profile_header({"display_name": "FULANA"})
    assert "Sem cargo público atual confirmado" in html
    assert "Partido não disponível" in html
    assert "ds-profile-chip" not in html


def test_name_title_case_keeps_particles_lower():
    assert title_case_name("MARIA DA SILVA E SOUZA") == "Maria da Silva e Souza"


def test_formats():
    assert format_reais("46366.19") == "R$ 46.366,19"
    assert format_reais("abc") is None
    assert format_full_date("2027-01-31") == "31/01/2027"
    assert format_full_date("2027-01") is None


def test_summary_cards_link_to_their_sections():
    profile = PROFILE | {
        "attendance_history": [
            {"period": "2023-02", "present": 7, "required": 8},
            {"period": "2026-10", "present": 3, "required": 3},
        ],
        "propositions": {"items": [
            {"kind": "PL", "occurred_on": "2026-03-26"},
            {"kind": "REQ", "occurred_on": "2026-08-31"},
        ]},
        "payments": [{"gross_amount": "46366.19", "competence": "2026-09"}],
        "assets": {"declarations": [{"election_year": 2026, "recorded_total": "15975.73"}]},
    }
    html = render_profile_summary(profile)
    assert "10 de 11 dias" in html and "fev/2023 a out/2026" in html
    assert "1 apresentadas" in html and "entre mar e ago/2026, na amostra" in html
    assert "R$ 46.366,19" in html and "bruto, referente a set/2026" in html
    assert "Bens declarados em 2026" in html and "R$ 15.975,73" in html
    assert "Ainda não coletado:</strong> gastos com gabinete" in html
    for anchor in ("presenca", "atuacao", "bens"):
        assert f'href="#{anchor}"' in html


def test_summary_marks_missing_data_as_unavailable_not_zero():
    html = render_profile_summary({})
    assert html.count("Não disponível") == 4
    assert " 0 " not in html


def test_section_navigation_lists_all_sections_in_order():
    html = render_section_navigation()
    positions = [html.index(f'href="#{anchor}"') for anchor, _ in PROFILE_SECTIONS]
    assert positions == sorted(positions)
    assert 'aria-label="Seções do perfil"' in html
