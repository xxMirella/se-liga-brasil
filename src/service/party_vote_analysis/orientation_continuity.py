"""Give the first dimension a comparable sign across legislatures.

An anchor legislature is one whose first dimension correlates strongly with the thematic
roll calls (direction fixed by the rubric). Other legislatures take their sign from the
correlation of individual scores of members present in both an oriented neighbour and
themselves, so a member keeps the same side when the governing coalition changes. The sign
is a single bit per legislature: it never changes distances inside a legislature.
"""

import numpy as np

ANCHOR_MINIMUM_CORRELATION = 0.4
CONTINUITY_MINIMUM_CORRELATION = 0.3
MINIMUM_SHARED_MEMBERS = 30


def is_thematic_anchor(pca: dict) -> bool:
    if pca.get("status") != "ok":
        return False
    return any(
        abs(value) >= ANCHOR_MINIMUM_CORRELATION
        for value in pca["orientation"][0]["correlation_with_thematic"].values()
        if value == value
    )


def shared_member_correlation(first: dict, second: dict) -> tuple[float, int]:
    shared = sorted(set(first) & set(second))
    if len(shared) < MINIMUM_SHARED_MEMBERS:
        return float("nan"), len(shared)
    left = np.array([first[m][0] for m in shared])
    right = np.array([second[m][0] for m in shared])
    return float(np.corrcoef(left, right)[0, 1]), len(shared)


def flip_first_dimension(pca: dict) -> None:
    for party in pca["parties"]:
        block = party["dimensions"][0]
        block["value"] = -block["value"]
        block["ci95"] = [-block["ci95"][1], -block["ci95"][0]]
    for scores in pca["_member_scores"].values():
        scores[0] = -scores[0]


def propagate_orientation(periods: list[dict]) -> None:
    """Annotate pca["first_dimension_orientation"] for every period of one chamber."""
    ordered = sorted(
        (p for p in periods if p["pca"].get("status") == "ok"),
        key=lambda period: period["legislature"],
    )
    resolved: dict[int, dict] = {}
    for period in ordered:
        if is_thematic_anchor(period["pca"]):
            resolved[period["legislature"]] = {"method": "thematic_anchor"}
    for _ in range(len(ordered)):
        for period in ordered:
            if period["legislature"] not in resolved:
                _try_continuity(period, ordered, resolved)
    for period in ordered:
        period["pca"]["first_dimension_orientation"] = resolved.get(
            period["legislature"], {"method": "unoriented", "comparable_across_legislatures": False}
        )


def _try_continuity(period: dict, ordered: list[dict], resolved: dict[int, dict]) -> None:
    best = None
    for other in ordered:
        if (
            other["legislature"] not in resolved
            or abs(other["legislature"] - period["legislature"]) != 1
        ):
            continue
        correlation, shared = shared_member_correlation(
            other["pca"]["_member_scores"], period["pca"]["_member_scores"]
        )
        if correlation == correlation and (best is None or abs(correlation) > abs(best[0])):
            best = (correlation, shared, other["legislature"])
    if best is None or abs(best[0]) < CONTINUITY_MINIMUM_CORRELATION:
        return
    if best[0] < 0:
        flip_first_dimension(period["pca"])
    resolved[period["legislature"]] = {
        "method": "member_continuity",
        "reference_legislature": best[2],
        "correlation_of_members_present_in_both": best[0],
        "shared_members": best[1],
        "sign_flipped": best[0] < 0,
    }


GOVERNMENT_AXIS_WARNING_CORRELATION = 0.7
MINIMUM_PARTIES_FOR_AXIS_CHECK = 6
MINIMUM_PARTY_MEMBERS = 8


def government_axis_check(period: dict) -> dict | None:
    """Correlate party first-dimension values with party agreement with the government.

    A high absolute correlation means the dimension mostly separates government from
    opposition (coalition behaviour) instead of a stable ideological axis.
    """
    alignment: dict[str, list[float]] = {}
    for row in period.get("government_alignment", []):
        pair = alignment.setdefault(row["party"], [0.0, 0.0])
        pair[0] += row["agreement"] * row["n_roll_calls"]
        pair[1] += row["n_roll_calls"]
    points = [
        (
            party["dimensions"][0]["value"],
            alignment[party["party"]][0] / alignment[party["party"]][1],
        )
        for party in period["pca"]["parties"]
        if party["n_members"] >= MINIMUM_PARTY_MEMBERS
        and alignment.get(party["party"], [0, 0])[1] >= 5
    ]
    if len(points) < MINIMUM_PARTIES_FOR_AXIS_CHECK:
        return None
    values, agreement = zip(*points, strict=True)
    correlation = float(np.corrcoef(values, agreement)[0, 1])
    return {
        "correlation": correlation,
        "n_parties": len(points),
        "dominated_by_government_opposition": abs(correlation)
        >= GOVERNMENT_AXIS_WARNING_CORRELATION,
    }
