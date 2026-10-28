"""Source dates, interims and party context must not become invented historical facts."""

from types import SimpleNamespace

import pytest

from crawlers.state_government.parsing import (
    parse_alesp_governor_chronology,
    parse_external_governor_mandates,
)
from service.state_government_history.collection import remove_documented_temporary_overlap
from service.state_government_history.document_text import document_text
from service.state_government_history.verified_periods import enrich_alckmin_membership


def artifact(tmp_path, content):
    path = tmp_path / "source.html"
    path.write_bytes(content.encode("latin1"))
    return SimpleNamespace(
        path=path,
        sha256="abc",
        fetched_at="2026-10-23T12:00:00Z",
        resource=SimpleNamespace(url="https://www.al.sp.gov.br/test"),
    )


def test_alesp_interim_inclusive_end_and_open_observation(tmp_path):
    source = artifact(
        tmp_path,
        '<meta charset="ISO-8859-1">Atualizado em 21/09/2012'
        "<table><tr><td>(14/06/2012 a17.06.2012)</td>"
        "<td>Guilherme Afif Domingos - VG</td></tr>"
        "<tr><td>01/01/2011 a</td><td>Geraldo Alckmin - GE</td></tr></table>",
    )
    temporary, holder = parse_alesp_governor_chronology(source)
    assert temporary["ends_before"] == "2012-06-18"
    assert temporary["exercise_kind"] == "temporary"
    assert holder["ends_before"] is None
    assert holder["observed_through"] == "2012-09-21"


def test_career_party_label_is_not_continuous_membership(tmp_path):
    source = artifact(
        tmp_path,
        "Mandatos Externos: Vice-Governador(a), RJ, Partido: PT, "
        "Período: 1999 a 2002; Governador(a), RJ, Partido: PDT, "
        "Período: 1998 a 2002. Atividades Profissionais",
    )
    records = parse_external_governor_mandates(source, "Pessoa")
    assert len(records) == 1
    assert records[0]["political_party_status"] == "unknown"
    assert records[0]["political_party_observations"][0]["abbreviation"] == "PDT"


def test_documented_interims_remove_holder_overlap_without_extending_terms():
    holder = dict(
        name="Titular", starts_on="2011-01-01", ends_before="2012-01-01", exercise_kind="holder"
    )
    interim = dict(
        name="Interino", starts_on="2011-06-01", ends_before="2011-06-03", exercise_kind="temporary"
    )
    rows = remove_documented_temporary_overlap([holder, interim])
    assert [(r["starts_on"], r["ends_before"]) for r in rows if r["name"] == "Titular"] == [
        ("2011-01-01", "2011-06-01"),
        ("2011-06-03", "2012-01-01"),
    ]


def test_waf_success_status_is_not_evidence(tmp_path):
    source = artifact(tmp_path, "Request unsuccessful. Incapsula incident ID: 123")
    with pytest.raises(ValueError, match="SOURCE_ACCESS_BLOCKED"):
        document_text(source)


def test_membership_proof_must_be_explicit_not_merely_party_name(tmp_path):
    source = artifact(tmp_path, "Geraldo Alckmin PSDB em uma cerimônia")
    with pytest.raises(ValueError, match="MEMBERSHIP_EVIDENCE_MISSING"):
        enrich_alckmin_membership([], source)


def test_annual_occurrence_does_not_invent_accession_or_party(tmp_path):
    from service.state_government_history.annual_observations import annual_observation

    source = artifact(tmp_path, "Governou em 2002, conforme registro anual.")
    row = annual_observation(source, "Pessoa", 2002, 2002, "Governou em 2002")
    assert row["date_precision"] == "year"
    assert "starts_on" not in row
    assert row["political_party_status"] == "unknown"


def test_open_old_chronology_does_not_assert_holder_remained_until_site_update(tmp_path):
    from service.state_government_history.collection import bound_chronology_exercises

    source = artifact(tmp_path, "Fonte oficial")
    row = dict(
        name="José Serra",
        starts_on="2007-01-01",
        ends_before=None,
        exercise_kind="holder",
        observed_through="2012-09-21",
        evidence=[],
    )
    result = bound_chronology_exercises([row], source, source)
    assert result[0]["observed_through"] == "2007-01-01"
    assert result[0]["ends_before"] is None


def test_legacy_state_office_codes_are_preserved_without_becoming_party_labels(tmp_path):
    source = artifact(
        tmp_path,
        "<table><tr><td>11/06/1891 a 15/12/1891</td>"
        "<td>Americo Braziliense de Almeida Mello - PECC - Termo de posse</td>"
        "</tr><tr><td>15/03/1975 a 15/03/1979</td>"
        "<td>Paulo Egydio Martins - GEAL - Termo de posse</td></tr></table>",
    )
    records = parse_alesp_governor_chronology(source, require_update=False)
    assert records[0]["starts_on"] == "1891-06-11"
    assert records[0]["source_office_code"] == "PECC"
    assert records[1]["source_office_code"] == "GEAL"
    assert all(row["political_party_status"] == "unknown" for row in records)


def test_same_day_historical_exercise_is_not_lost_as_empty_interval(tmp_path):
    source = artifact(
        tmp_path,
        "<table><tr><td>15/12/1891 a 15/12/1891</td>"
        "<td>Sergio Tertuliano Castello Branco - PI</td></tr></table>",
    )
    record = parse_alesp_governor_chronology(source, require_update=False)[0]
    assert record["starts_on"] == "1891-12-15"
    assert record["ends_before"] == "1891-12-16"
