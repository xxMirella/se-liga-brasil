"""A party difference is a verification trigger, not a new person or inferred date."""

from service.political_party_verification.changes import verify_monthly_political_parties


def observations():
    return [
        {
            "person_id": "p",
            "competence": "2026-10-01",
            "political_party_code": "13",
            "source_record_id": 1,
        },
        {
            "person_id": "p",
            "competence": "2026-11-01",
            "political_party_code": "22",
            "source_record_id": 2,
        },
    ]


def test_monthly_difference_requires_history_evidence():
    result = verify_monthly_political_parties(observations(), [])
    assert result[1]["status"] == "change_requires_verification"
    assert result[1]["previous_political_party_code"] == "13"
    assert result[1]["verification_through"] == "2026-11-30"
    assert result[1]["person_id"] == "p"


def test_confirmed_reported_change_preserves_actual_source_date():
    report = {
        "person_id": "p",
        "political_party_code": "22",
        "starts_on": "2026-11-15",
        "source_record_id": 3,
    }
    result = verify_monthly_political_parties(observations(), [report])
    assert result[1]["status"] == "reported_change_confirmed"
    assert result[1]["evidence_source_record_ids"] == [3]
    assert report["starts_on"] == "2026-11-15"


def test_future_membership_cannot_confirm_past_payroll_difference():
    report = {
        "person_id": "p",
        "political_party_code": "22",
        "starts_on": "2026-12-01",
        "source_record_id": 3,
    }
    assert (
        verify_monthly_political_parties(observations(), [report])[1]["status"]
        == "change_requires_verification"
    )
