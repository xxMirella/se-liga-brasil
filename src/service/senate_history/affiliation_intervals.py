"""Validate dated parliamentary affiliation records without inferring civil membership."""

from datetime import date, timedelta


def parliamentary_affiliation_intervals(payload, senator_code):
    parliamentary = payload["FiliacaoParlamentar"]["Parlamentar"]
    if str(parliamentary["Codigo"]) != str(senator_code):
        raise ValueError("SENATOR_SOURCE_ID_MISMATCH")
    affiliations = parliamentary["Filiacoes"]["Filiacao"]
    if isinstance(affiliations, dict):
        affiliations = [affiliations]
    intervals = sorted((_affiliation_interval(row) for row in affiliations),
                       key=lambda row: row["valid_from"])
    for previous, current in zip(intervals, intervals[1:], strict=False):
        if previous["valid_until"] is None or previous["valid_until"] > current["valid_from"]:
            raise ValueError("OVERLAPPING_PARLIAMENTARY_AFFILIATIONS")
    return intervals


def _affiliation_interval(row):
    starts_on = date.fromisoformat(row["DataFiliacao"])
    ends_on = date.fromisoformat(row["DataDesfiliacao"]) if row.get("DataDesfiliacao") else None
    if ends_on is not None and ends_on < starts_on:
        raise ValueError("INVALID_PARLIAMENTARY_AFFILIATION_INTERVAL")
    return {
        "political_party": row["Partido"]["SiglaPartido"],
        "source_political_party_code": row["Partido"]["CodigoPartido"],
        "valid_from": starts_on.isoformat(),
        "valid_until": (ends_on + timedelta(days=1)).isoformat() if ends_on else None,
        "date_precision": "day",
        "meaning": "senate_parliamentary_registration_not_civil_membership_certificate",
    }
