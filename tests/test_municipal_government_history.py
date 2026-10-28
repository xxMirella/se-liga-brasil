"""Municipal exercise boundaries must survive archival parsing and known substitutions."""

import json
from datetime import date
from types import SimpleNamespace

import pytest

from crawlers.municipal_government.parsing import (
    parse_sp_dossier,
    reconcile_documented_handover_dates,
    sp_dossier_row,
)
from crawlers.municipal_government.rio_parsing import parse_rio_crivella_and_succession
from normalization.executive_intervals import remove_documented_temporary_overlap
from service.political_dashboard_dataset.executive import build_annual_executive_partitions


def source(tmp_path, content):
    path = tmp_path / "source.html"
    path.write_text(content)
    return SimpleNamespace(
        path=path,
        sha256="abc",
        fetched_at="2026-10-23T12:00:00Z",
        resource=SimpleNamespace(url="https://www.saopaulo.sp.leg.br/source"),
    )


def test_sp_dossier_reads_exercise_before_election_context(tmp_path):
    artifact = source(tmp_path, "")
    block = (
        "João Dória\n(João Agripino da Costa Dória Junior)\n01/01/2017\na\n06/04/2018\n"
        "Eleito em 02/10/2016. Vice-prefeito: Bruno Covas"
    )
    row = sp_dossier_row(block, artifact, "55")
    assert row["name"] == "João Dória"
    assert row["starts_on"] == "2017-01-01"
    assert row["political_party_status"] == "unknown"
    successor = dict(starts_on="2018-04-06", ends_before="2021-01-01")
    assert reconcile_documented_handover_dates([row, successor])[0]["ends_before"] == "2018-04-06"


def test_dossier_open_exercise_is_bounded_by_document_observation(tmp_path):
    artifact = source(tmp_path, "")
    row = sp_dossier_row(
        "Ricardo Nunes\n(Ricardo Luís Reis Nunes)\nDesde\n16/05/2021", artifact, "58"
    )
    assert row["starts_on"] == "2021-05-16"
    assert row["ends_before"] is None
    assert row["observed_through"] == "2023-08-30"


def test_new_dossier_revision_requires_review(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "crawlers.municipal_government.parsing.document_text",
        lambda artifact: "Atualizado até: 30/08/2026",
    )
    with pytest.raises(ValueError, match="VERSION_REQUIRES_REVIEW"):
        parse_sp_dossier(source(tmp_path, ""))


def test_2020_removal_and_interim_do_not_extend_to_current_year(tmp_path):
    text = (
        "Capital do Estado do Rio de Janeiro - Marcelo Bezerra Crivella é o prefeito "
        "(01/01/2017-22/12/2020). Jorge Felippe (DEM), assume como ‘prefeito em exercício’"
    )
    artifact = source(tmp_path, json.dumps([{"ano": "2020", "rio": text}]))
    crivella, felippe = parse_rio_crivella_and_succession(artifact)
    assert crivella["ends_before"] == "2020-12-22"
    assert felippe["starts_on"] == "2020-12-22"
    assert felippe["ends_before"] is None
    assert build_annual_executive_partitions([crivella, felippe], 2026, date(2026, 10, 23)) == []


def test_open_holder_and_interim_are_not_counted_simultaneously_at_year_end():
    holder = dict(
        name="Titular",
        territory_code="3550308",
        institution_code="municipal_government",
        starts_on="2021-05-16",
        ends_before=None,
        observed_through="2026-10-01",
        exercise_kind="holder",
        date_precision="day",
    )
    interim = dict(
        holder,
        name="Interino",
        starts_on="2021-12-29",
        ends_before="2022-01-05",
        exercise_kind="temporary",
    )
    rows = remove_documented_temporary_overlap([holder, interim])
    assert (
        build_annual_executive_partitions(rows, 2021, date(2026, 10, 23))[0]["current"]["name"]
        == "Interino"
    )
    assert (
        build_annual_executive_partitions(rows, 2022, date(2026, 10, 23))[0]["current"]["name"]
        == "Titular"
    )
    assert rows[-2]["ends_before"] is None


def test_substitution_in_one_city_does_not_remove_another_city_holder():
    holder = dict(
        name="Titular",
        territory_code="3550308",
        institution_code="municipal_government",
        starts_on="2021-01-01",
        ends_before="2022-01-01",
        exercise_kind="holder",
    )
    interim = dict(
        holder, territory_code="3304557", starts_on="2021-12-29", exercise_kind="temporary"
    )
    rows = remove_documented_temporary_overlap([holder, interim])
    assert rows[0]["starts_on"] == "2021-01-01"
    assert rows[0]["ends_before"] == "2022-01-01"
