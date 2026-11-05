"""Reviewed interruptions cannot manufacture exercise, vacancies or future classifications."""

import hashlib
import json
from copy import deepcopy

import pytest

from crawlers.camara.reviewed_year_end_evidence import load_reviewed_year_end_cases
from service.political_dashboard.camara_orientation import (
    chamber_orientation_summary,
    render_chamber_reconciliation,
)
from service.political_dashboard.orientation_composition import (
    orientation_composition,
    render_orientation_composition_note,
)
from service.political_dashboard_dataset.chamber_reviewed_interruptions import (
    apply_reviewed_cases,
    reviewed_snapshot_cases,
)
from service.political_dashboard_dataset.history import reduce_composition


def review_fixture():
    signature = {"situacao": "Licença", "dataHora": "2015-12-15T11:51"}
    members = [{"source_person_id": "active", "uf": "RJ"}]
    case = {"year": 2015, "uf": "RJ", "kind": "licensed_awaiting_possession",
            "events": [{"source_person_id": "licensed", "signature": signature}],
            "detail": "Licença comprovada; posse posterior à fotografia.",
            "uf_member_ids_sha256": hashlib.sha256(b'["active"]').hexdigest(),
            "evidence_assertions": [{"source": {"url": "https://www.camara.leg.br/",
                                                "sha256": "a" * 64}}]}
    histories = [{"official_deputy_id": "licensed", "events": [signature]}]
    rows = [{"uf": "RJ", "unresolved": 1, "documented_vacancies": 0}]
    return case, histories, members, rows


@pytest.mark.parametrize("change,error", [
    ("member", "UF_MEMBERS_CHANGED"), ("event", "EVENT_CHANGED"),
    ("deficit", "NO_LONGER_MATCHES_DEFICIT"), ("duplicate", "NO_LONGER_MATCHES_DEFICIT"),
])
def test_review_fails_closed_when_the_reviewed_snapshot_changes(change, error):
    case, histories, members, rows = review_fixture()
    cases = [case]
    if change == "member":
        members[0]["source_person_id"] = "different_person"
    elif change == "event":
        histories[0]["events"] = []
    elif change == "deficit":
        rows[0]["unresolved"] = 0
    else:
        cases.append(deepcopy(case))
    with pytest.raises(ValueError, match=error):
        reviewed_snapshot_cases(cases, histories, members, rows, 2015)


def test_license_is_accounted_separately_without_creating_a_person_or_vacancy():
    case, histories, members, rows = review_fixture()
    verified = reviewed_snapshot_cases([case], histories, members, rows, 2015)
    vacancies = []
    interruptions, result = apply_reviewed_cases(verified, vacancies, rows)
    assert len(members) == 1
    assert vacancies == []
    assert result[0]["unresolved"] == 0
    assert result[0]["documented_exercise_interruptions"] == 1
    assert rows[0]["unresolved"] == 1
    assert interruptions[0]["kind"] == "licensed_awaiting_possession"


def test_archived_review_requires_official_source_hash_and_exact_text(tmp_path):
    raw = b'<html><p>Posse em <strong>06/01/2016</strong>.</p></html>'
    digest = hashlib.sha256(raw).hexdigest()
    archive = tmp_path / (digest + ".html")
    archive.write_bytes(raw)
    source = {"url": "https://www.camara.leg.br/deputados/1/biografia",
              "sha256": digest, "http_status": 200}
    assertion = {"source": source, "archive": archive.name, "contains": "06/01/2016"}
    review = tmp_path / "review.json"
    review.write_text(json.dumps([{"evidence_assertions": [assertion]}]))
    assert len(load_reviewed_year_end_cases(review, tmp_path)) == 1
    archive.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="HASH_MISMATCH"):
        load_reviewed_year_end_cases(review, tmp_path)
    archive.write_bytes(raw)
    assertion["contains"] = "01/01/2016"
    review.write_text(json.dumps([{"evidence_assertions": [assertion]}]))
    with pytest.raises(ValueError, match="ASSERTION_MISMATCH"):
        load_reviewed_year_end_cases(review, tmp_path)


def chamber(groups, year=2018):
    return {"institution_code": "camara", "territory_code": "BR", "expected_seats": 513,
            "orientation_policy_version": "camara_2010_2019.v2", "snapshot_on": f"{year}-12-31",
            "year": year, "total": sum(groups.values()),
            "political_parties": [{"abbreviation": key, "count": count}
                                  for key, count in groups.items()]}


def test_chart_uses_the_same_historical_name_alignments_as_the_summary():
    original = chamber({"PATRI": 5, "DEM": 369, "PT": 124})
    chart = orientation_composition(original, 2018)
    summary = chamber_orientation_summary(original, 2018)
    actual = {row["orientation_category"]: row["count"] for row in chart["political_parties"]}
    assert actual["right"] == summary["counts"]["right"] == 374
    assert sum(actual.values()) == original["total"]
    assert original["political_parties"][0]["abbreviation"] == "PATRI"


def test_interruption_survives_history_reduction_and_never_counts_as_a_vote():
    composition = chamber({"DEM": 256, "PT": 256}, year=2019)
    composition["documented_exercise_interruptions"] = [{"uf": "PB", "detail": "Afastado"}]
    summary = chamber_orientation_summary(composition, 2019)
    assert summary["unobserved_seats"] == 0
    assert summary["documented_vacant_seats"] == 0
    assert summary["documented_exercise_interruptions"] == 1
    assert summary["absolute_majority"] is None
    assert summary["absence_proven"] is True
    reduced = dict(institution_code="camara", territory_code="BR", **reduce_composition({
        "institution_code": "camara", "composition": composition,
    }))
    assert chamber_orientation_summary(reduced, 2019) == summary


def test_pre_survey_year_note_does_not_claim_future_survey_classification():
    note = render_orientation_composition_note(chamber({"PT": 513}, 2010), 2010, None)
    assert "Sem classificação datada integrada" in note
    assert "Survey de 2018" not in note


def test_resolved_details_include_sources_and_escaped_names():
    case, histories, members, rows = review_fixture()
    case["detail"] = "<script>not markup</script>"
    verified = reviewed_snapshot_cases([case], histories, members, rows, 2015)
    interruptions, uf_rows = apply_reviewed_cases(verified, [], rows)
    uf_rows[0].update(observed_people=45, expected_seats=46)
    html = render_chamber_reconciliation({"uf_reconciliation": uf_rows,
                                          "documented_exercise_interruptions": interruptions})
    assert "&lt;script&gt;" in html
    assert "https://www.camara.leg.br/" in html
    assert "0 pendências" in html
