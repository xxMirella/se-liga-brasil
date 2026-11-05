from datetime import date

import pytest

from crawlers.camara.attendance import parse_attendance_days
from service.ingestion.contracts import IngestionError
from service.public_profile_web.profile import render_profile_header
from service.public_profile_web.profile_attendance import render_attendance


def attendance_html(total=1, status="Presença"):
    return f"""<table><tr><td>02/02/2026</td><td></td><td>{status}</td></tr>
    <tr><td>EXTRAORDINÁRIA Nº001 -02/02/2026</td><td>Presença</td></tr>
    <tr><td>Total de dias com sessões deliberativas realizadas no período</td>
    <td>{total}</td></tr></table>""".encode()


def test_sessions_do_not_duplicate_days():
    days = parse_attendance_days(attendance_html(), 2026, date(2026, 10, 18))
    assert days == {date(2026, 2, 2): "present"}


def test_missing_day_fails_instead_of_inflating_percentage():
    with pytest.raises(IngestionError, match="INCOMPLETE_DAYS"):
        parse_attendance_days(attendance_html(total=2), 2026, date(2026, 10, 18))


def test_justified_absence_is_not_presence():
    days = parse_attendance_days(
        attendance_html(status="Ausência justificada"), 2026, date(2026, 10, 18)
    )
    assert days[date(2026, 2, 2)] == "excused_absence"


def test_profile_shows_basis_and_education():
    profile = {"education_level": "Superior completo", "attendance": {
        "percentage": "80.0", "period": "2026-09", "present": 8, "required": 10,
    }}
    assert "superior completo" in render_profile_header(profile)


def test_unavailable_is_not_zero():
    assert "Não disponível" in render_attendance({})
    assert "0%" not in render_attendance({})


def test_attendance_section_keeps_missing_months_and_percentages_distinct():
    from service.public_profile_web.profile_attendance import render_attendance_section

    html = render_attendance_section({"attendance_history": [
        {"period": "2025-03", "present": 9, "required": 9, "percentage": "100.0"},
        {"period": "2025-04", "present": 6, "required": 12, "percentage": None},
    ]})
    assert 'id="presenca"' in html and "ds-profile-month--empty" in html
    assert "sem percentual oficial" in html and "Em 1 mês, a fonte não publicou" in html
    assert ">0%" not in html and " 0%" not in html


def test_attendance_section_without_history_is_not_zero():
    from service.public_profile_web.profile_attendance import render_attendance_section

    html = render_attendance_section({})
    assert 'id="presenca"' in html and "Sem frequência consolidada" in html
    assert "0%" not in html


def test_career_section_escapes_and_orders_offices():
    from service.public_profile_web.profile_career import render_career_section

    html = render_career_section({
        "political_party": {"abbreviation": "<b>X</b>"},
        "current_offices": [
            {"office_kind": "federal_deputy", "represented_uf": "SP", "starts_on": "2023-02-01",
             "institution": {"name": "Câmara dos Deputados"}},
        ],
    })
    assert 'id="trajetoria"' in html and "2023 – hoje" in html
    assert "&lt;b&gt;X&lt;/b&gt;" in html and "<b>X</b>" not in html
