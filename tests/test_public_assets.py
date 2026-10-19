"""Public assets preserve uncertainty and exclude personal free-form identifiers."""

from contextlib import nullcontext
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from service.public_profile.assets import get_public_assets, official_asset_url
from service.public_profile.contracts import PublicProfileError

PERSON_ID = str(uuid4())
TODAY = date(2026, 10, 18)


class AssetsRepository:
    def __init__(self, value=Decimal("120.50")):
        self.person = {"person_id": PERSON_ID}
        self.years = [
            {
                "election_year": 2022,
                "item_count": 1,
                "recorded_total": value,
                "review_count": int(value < 0),
                "source_generated_at": datetime(2022, 9, 1, tzinfo=UTC),
            }
        ]
        self.items = [
            {
                "election_year": 2022,
                "asset_type": "Apartamento",
                "declared_value": value,
                "value_quality_status": "reported",
                "source_url": "https://dadosabertos.tse.jus.br/dataset/bens",
                "description": "PRIVATE CPF ACCOUNT ADDRESS",
                "candidate_sequence": "PRIVATE ID",
            }
        ]
        self.item_calls = 0

    def read_snapshot(self):
        return nullcontext()

    def fetch_person(self, person_id):
        return self.person

    def fetch_asset_years(self, person_id, as_of):
        return self.years

    def fetch_asset_items(self, person_id, years):
        self.item_calls += 1
        return self.items


def test_public_assets_exposes_recorded_values_without_current_wealth_claim():
    result = get_public_assets(AssetsRepository(), PERSON_ID, TODAY)
    declaration = result["declarations"][0]
    assert declaration["recorded_total"] == "120.50"
    assert declaration["election_year"] == 2022
    assert declaration["coverage"] == "completeness_unverified"
    assert result["current_net_worth"]["value"] is None
    assert "PRIVATE" not in str(result)


def test_missing_records_is_unknown_and_skips_item_query():
    repository = AssetsRepository()
    repository.years = []
    result = get_public_assets(repository, PERSON_ID, TODAY)
    assert result["coverage"]["status"] == "unknown"
    assert result["declarations"] == []
    assert repository.item_calls == 0


def test_signed_values_preserved_and_flagged():
    result = get_public_assets(AssetsRepository(Decimal("-12.00")), PERSON_ID, TODAY)
    assert result["declarations"][0]["recorded_total"] == "-12.00"
    assert result["declarations"][0]["value_quality_status"] == "requires_review"


def test_item_limit_never_presents_subset_sum_as_complete():
    repository = AssetsRepository()
    repository.years[0]["item_count"] = 101
    result = get_public_assets(repository, PERSON_ID, TODAY)
    assert result["declarations"][0]["items_truncated"] is True
    assert result["declarations"][0]["total_scope"] == "available_records_only"


def test_person_not_found():
    repository = AssetsRepository()
    repository.person = None
    with pytest.raises(PublicProfileError):
        get_public_assets(repository, PERSON_ID, TODAY)


@pytest.mark.parametrize(
    "url",
    [
        "https://tse.jus.br.evil.test/file",
        "http://tse.jus.br/f",
        "https://user:pass@tse.jus.br/f",
        "javascript:alert(1)",
        None,
    ],
)
def test_untrusted_source_urls_are_not_published(url):
    assert official_asset_url(url) is None
