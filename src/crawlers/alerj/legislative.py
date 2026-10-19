"""Explicit unavailable legislative capability until a source contract is validated."""


def legislative_capability(domain, start, end):
    return {
        "institution": "alerj",
        "domain": domain,
        "requested_start": start.isoformat(),
        "requested_end": end.isoformat(),
        "status": "unsupported",
        "reason": "LEGISLATIVE_CONTRACT_NOT_VALIDATED",
        "source_coverage_start": None,
        "source_coverage_end": None,
    }
