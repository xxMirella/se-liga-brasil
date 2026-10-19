"""Date/jurisdiction boundaries must not imply performance or historical validity."""

import json
from datetime import date

import pytest

from service.office_duties import get_office_duties
from service.office_duties.catalog import CATALOGS, REVIEWED_ON


@pytest.mark.parametrize("office_kind,jurisdiction", CATALOGS)
def test_reviewed_catalog_has_official_sources_and_collective_scope(office_kind, jurisdiction):
    result = get_office_duties(office_kind, jurisdiction, as_of=REVIEWED_ON)
    assert result["status"] == "reviewed_summary"
    assert result["legal_valid_from"] is None
    assert result["legal_valid_through"] is None
    assert result["items"]
    assert len({item["code"] for item in result["items"]}) == len(result["items"])
    for item in result["items"]:
        assert item["scope"] == "collective_institution"
        assert all(source["url"].startswith("https://") for source in item["sources"])
        assert all(source["reference"] for source in item["sources"])
    json.dumps(result)


@pytest.mark.parametrize(
    "as_of,status",
    [
        (date(2024, 1, 1), "historical_not_verified"),
        (date(2027, 1, 1), "review_required"),
    ],
)
def test_catalog_does_not_invent_legal_validity(as_of, status):
    result = get_office_duties("senator", "BR", as_of=as_of)
    assert result["status"] == status
    assert result["items"] == []


def test_other_state_does_not_receive_sp_rules():
    result = get_office_duties("state_deputy", "MG", as_of=REVIEWED_ON)
    assert result["status"] == "not_cataloged"
    assert result["items"] == []


def test_municipal_baseline_requires_explicit_national_scope():
    assert get_office_duties("councillor", "BR:SP:3550308", as_of=REVIEWED_ON)["items"] == []
    result = get_office_duties("councillor", "BR", as_of=REVIEWED_ON)
    assert "lei orgânica" in " ".join(result["limitations"])


def test_response_mutation_does_not_change_catalog():
    first = get_office_duties("senator", "BR", as_of=REVIEWED_ON)
    first["items"][0]["sources"][0]["title"] = "modified"
    first["limitations"].clear()
    second = get_office_duties("senator", "BR", as_of=REVIEWED_ON)
    assert second["items"][0]["sources"][0]["title"] != "modified"
    assert second["limitations"]


@pytest.mark.parametrize("as_of", [None, "2026-10-18"])
def test_requires_explicit_date(as_of):
    with pytest.raises(ValueError, match="INVALID_DUTIES_DATE"):
        get_office_duties("senator", "BR", as_of=as_of)
