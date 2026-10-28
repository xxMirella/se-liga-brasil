"""Expose annual party changes separately from presidential exercise dates."""


def annual_executive_party_periods(exercise, year):
    start, end = f"{year}-01-01", f"{year + 1}-01-01"
    return [
        dict(
            period,
            starts_on=max(period["starts_on"], start),
            ends_before=min(period["ends_before"], end),
        )
        for period in exercise.get("political_party_periods", [])
        if period["starts_on"] < end and period["ends_before"] > start
    ]


def party_at_annual_reference(periods):
    """A party observed earlier in the year must not silently fill its end."""
    latest = max(periods, key=lambda period: period["ends_before"])
    return {
        "political_party": latest["political_party"],
        "political_party_code": latest.get("political_party_code"),
        "political_party_status": latest["political_party_status"],
        "political_party_evidence": latest["evidence"],
        "political_party_context": latest.get("political_party_context"),
        "political_party_limitation": latest.get("political_party_limitation"),
        "political_party_reference": "last_documented_party_period_during_exercise_in_year",
        "political_party_periods": periods,
    }
