from datetime import date

import pytest

from crawlers.camara.attendance import parse_attendance_days
from service.ingestion.contracts import IngestionError
from service.public_profile_web.profile import render_attendance, render_profile_header


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
    html = render_profile_header({"education_level": "Superior completo", "attendance": {
        "percentage": "80.0", "period": "2026-09", "present": 8, "required": 10,
    }})
    assert "Superior completo" in html
    assert "80,0%" in html
    assert "8 de 10 dias com sessões deliberativas" in html
    assert "Presença em plenário" in html


def test_unavailable_is_not_zero():
    assert "Não disponível" in render_attendance({})
    assert "0%" not in render_attendance({})
