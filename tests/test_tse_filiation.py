"""A missing public contract must not generate invented facts or N+1 requests."""

from crawlers.tse_filiation.enrichment import collect_tse_filiation


class ForbiddenAccess:
    def __getattr__(self, name):
        raise AssertionError(f"Unexpected access: {name}")


def test_unavailable_nominal_source_is_blocked_once_without_io():
    people = {f"internal-person-{index}": {"current_political_party"} for index in range(1000)}
    result = collect_tse_filiation(ForbiddenAccess(), ForbiddenAccess(), people)
    assert result["status"] == "blocked"
    assert result["requires_source_validation"]
    assert result["target_people"] == 1000
    assert result["network_requests"] == result["ingested_facts"] == 0
    assert len(result["failures"]) == 1
    assert result["failures"][0]["retry_after_seconds"] == 604800
    assert result["requested_fields"] == ["current_political_party"]
    assert not result["unsupported_fields"]


def test_empty_affiliation_batch_does_not_block_other_work():
    assert collect_tse_filiation(None, None, {}) == {
        "status": "completed",
        "target_people": 0,
        "failures": [],
    }


def test_unsupported_domain_is_reported_without_claiming_coverage():
    result = collect_tse_filiation(None, None, {"internal-person": set()}, {"current_salary"})
    assert result["unsupported_fields"] == ["current_salary"]
    assert result["status"] == "blocked"
