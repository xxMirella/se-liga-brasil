"""Cabinet costs reconcile by role and month, without mistaking staff for senators."""

import csv
import io
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from crawlers.senado.cabinet_collection import discover_staff_months, verified_cabinet_index
from crawlers.senado.cabinet_payroll import (
    HEADERS,
    aggregate_staff_payroll,
    cabinet_month_record,
)
from service.cabinet_payroll.public_projection import public_cabinet_payroll
from service.ingestion.contracts import IngestionError
from service.public_profile_web.cabinet_payroll import render_cabinet_cost


def staff_row(**overrides):
    row = dict.fromkeys(HEADERS, "0")
    row.update(
        {
            "VÍNCULO": "COMISSIONADO",
            "CATEGORIA": "CARGO EM COMISSÃO",
            "CARGO": "ASSESSOR PARLAMENTAR",
            "TIPO FOLHA": "Normal",
            "LOTAÇÃO EXERCÍCIO": "Gabinete da Senadora Pessoa Exemplo",
            "REMUN_BASICA": "1000",
            "IMPOSTO_RENDA": "-100",
            "PREVIDÊNCIA": "-50",
            "REM_LIQUIDA": "850",
            "AUXÍLIOS": "200",
        }
    )
    return row | overrides


def payroll_csv(rows):
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(["ÚLTIMA ATUALIZAÇÃO", "30/09/2026 05:00"])
    writer.writerow(HEADERS)
    writer.writerows([[row[key] for key in HEADERS] for row in rows])
    return output.getvalue().encode("latin1")


def example_month(period="2026-09"):
    cabinets, _ = aggregate_staff_payroll(payroll_csv([staff_row()]), period)
    artifact = SimpleNamespace(
        resource=SimpleNamespace(url="https://www.senado.leg.br/test.csv"),
        sha256="a" * 64,
        fetched_at="2026-10-22T15:00:00+00:00",
    )
    return cabinet_month_record("private-uuid", period, cabinets["pessoa exemplo"], artifact)


def test_multiple_payroll_types_add_without_double_counting_deductions():
    rows = [
        staff_row(),
        staff_row(**{"TIPO FOLHA": "Suplementar"}),
        staff_row(**{"CARGO": "SECRETÁRIO PARLAMENTAR"}),
        staff_row(**{"CATEGORIA": "PARLAMENTAR"}),
        staff_row(**{"LOTAÇÃO EXERCÍCIO": "Liderança do Governo"}),
    ]
    cabinets, skipped = aggregate_staff_payroll(payroll_csv(rows), "2026-09")
    role = cabinets["pessoa exemplo"]["ASSESSOR PARLAMENTAR"]
    assert role["gross_amount"] == Decimal("2000.00")
    assert role["total_amount"] == Decimal("2400.00")
    assert role["payment_entries"] == 2
    assert skipped == {"parliamentary_payments": 1, "other_organizational_units": 1}


@pytest.mark.parametrize(
    "changes",
    [
        {"REM_LIQUIDA": "999"},
        {"CARGO": ""},
        {"REMUN_BASICA": "nan"},
    ],
)
def test_bad_staff_row_blocks_incomplete_month(changes):
    with pytest.raises(IngestionError):
        aggregate_staff_payroll(payroll_csv([staff_row(**changes)]), "2026-09")


def test_fraction_without_leading_zero_and_negative_adjustments_are_preserved():
    row = staff_row(**{"OUTRAS_EVENTUAIS": ",2", "REM_LIQUIDA": "850,20", "AUXÍLIOS": "-10"})
    cabinets, _ = aggregate_staff_payroll(payroll_csv([row]), "2026-09")
    assert cabinets["pessoa exemplo"]["ASSESSOR PARLAMENTAR"]["total_amount"] == Decimal("990.20")


def test_source_schema_and_explicit_month_are_required():
    with pytest.raises(IngestionError, match="SCHEMA_CHANGED"):
        aggregate_staff_payroll(b"not a payroll", "2026-09")
    with pytest.raises(IngestionError, match="INVALID_PAYROLL_MONTH"):
        aggregate_staff_payroll(payroll_csv([staff_row()]), "2026-13")


def test_discovery_uses_only_published_official_months():
    path = "/transparencia/LAI/secrh/SF_ConsultaRemuneracaoServidoresParlamentares_202609.csv"
    assert discover_staff_months(f'<a href="{path}">Setembro</a>'.encode())[0][0] == "2026-09"
    with pytest.raises(IngestionError, match="UNTRUSTED_RESOURCE_URL"):
        discover_staff_months(f'<a href="https://evil.example{path}">Setembro</a>'.encode())
    with pytest.raises(IngestionError, match="NOT_PUBLISHED"):
        discover_staff_months(f'<a href="{path}">Setembro</a>'.encode(), ["2026-08"])


def test_attribution_requires_unique_verified_civil_name_and_official_parliamentary_name():
    member = {
        "IdentificacaoParlamentar": {
            "NomeCompletoParlamentar": "Pessoa Civil Exemplo",
            "NomeParlamentar": "Pessoa Exemplo",
        }
    }
    person = {"person_id": "p", "civil_name": "Pessoa Civil Exemplo", "source_record_id": 1}
    assert verified_cabinet_index([member], [person]) == {"pessoa exemplo": person}
    assert verified_cabinet_index([member], [person, person | {"person_id": "homonym"}]) == {}


def test_public_history_sums_only_available_months_and_hides_identity_evidence():
    months = [example_month(), example_month("2026-07")]
    months[0]["identityEvidence"] = "PRIVATE"
    public = public_cabinet_payroll({"months": months, "truncated": False})
    assert public["latest"]["total_amount"] == "1200.00"
    assert public["totals_by_role"][0]["total_amount"] == "2400.00"
    assert "private-uuid" not in str(public) and "PRIVATE" not in str(public)
    html = render_cabinet_cost({"cabinet_payroll": public})
    assert "R$ 1.200,00" in html and "R$ 2.400,00" in html
    assert 'commandfor="cabinet-payroll-history"' in html
    assert "2026-09" in html and "2026-07" in html and "2026-08" not in html
    assert "Meses ausentes não significam gasto zero" in html


def test_role_text_is_escaped_and_missing_cost_is_never_zero():
    month = example_month()
    month["roles"][0]["role"] = "<script>bad()</script>"
    html = render_cabinet_cost(
        {"cabinet_payroll": public_cabinet_payroll({"months": [month], "truncated": False})}
    )
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert "Não disponível" in render_cabinet_cost({})


def test_history_query_bounds_months_and_respects_reference_date():
    from unittest.mock import Mock

    from database.cabinet_payroll import fetch_cabinet_payroll_history

    connection = Mock()
    connection.execute.return_value.fetchall.return_value = [{"payroll": example_month()}] * 121
    result = fetch_cabinet_payroll_history(connection, "uuid", date(2026, 9, 30))
    assert len(result["months"]) == 120 and result["truncated"]
    assert connection.execute.call_args.args[1] == ("uuid", "2026-09")


@pytest.mark.parametrize(
    "lotation",
    [
        "Escritório de Apoio 1 da Senadora Pessoa Exemplo",
        "Escritório de Apoio nº1 da Senadora Pessoa Exemplo",
        "Escritório de Ap. 1 Sen. Pessoa Exemplo",
        "Escritório Apoio 1 da Senadora Pessoa Exemplo",
    ],
)
def test_support_offices_are_added_to_same_cabinet_without_matching_other_departments(lotation):
    rows = [
        staff_row(),
        staff_row(**{"LOTAÇÃO EXERCÍCIO": lotation}),
        staff_row(**{"LOTAÇÃO EXERCÍCIO": "Serviço de Apoio às Contratações de TI"}),
    ]
    cabinets, skipped = aggregate_staff_payroll(payroll_csv(rows), "2026-09")
    assert cabinets["pessoa exemplo"]["ASSESSOR PARLAMENTAR"]["total_amount"] == Decimal("2400.00")
    assert skipped == {"other_organizational_units": 1}


def test_absence_deductions_reduce_cost_but_tax_and_pension_are_not_deducted_twice():
    row = staff_row(**{"FALTAS": "-50", "REM_LIQUIDA": "800"})
    cabinets, _ = aggregate_staff_payroll(payroll_csv([row]), "2026-09")
    amounts = cabinets["pessoa exemplo"]["ASSESSOR PARLAMENTAR"]
    assert amounts["gross_amount"] == Decimal("950.00")
    assert amounts["total_amount"] == Decimal("1150.00")
