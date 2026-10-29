"""Party positions from member ideal points, with column-bootstrap uncertainty.

Party position = mean of the ideal points of the (member, party) rows estimated while the
member was affiliated to that party. Units: standard deviations of the legislature's rows, so
values are comparable only inside one chamber and legislature.
"""

from dataclasses import dataclass

import numpy as np

from service.party_vote_analysis.ideal_points import align_to_reference, fit_ideal_points
from service.party_vote_analysis.member_matrix import VoteMatrix

MINIMUM_ROWS_PER_PARTY = 3
MINIMUM_THEMATIC_ROWS = 30
MINIMUM_THEMATIC_COLUMNS = 3
DIMENSIONS = 2


@dataclass(frozen=True)
class Orientation:
    signs: np.ndarray  # one multiplier per dimension
    notes: list[dict]  # correlation with thematic scores, per dimension


def thematic_member_scores(matrix: VoteMatrix, columns: np.ndarray, signs: np.ndarray):
    """Mean pole-signed vote per row over thematic roll calls; NaN when none was cast."""
    if len(columns) == 0:
        return np.full(len(matrix.row_keys), np.nan)
    signed = matrix.values[:, columns] * signs
    counts = (~np.isnan(signed)).sum(axis=1)
    totals = np.nansum(signed, axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(counts > 0, totals / counts, np.nan)


def _correlation(left: np.ndarray, right: np.ndarray) -> float:
    valid = ~(np.isnan(left) | np.isnan(right))
    if valid.sum() < MINIMUM_THEMATIC_ROWS or np.std(right[valid]) == 0:
        return float("nan")
    return float(np.corrcoef(left[valid], right[valid])[0, 1])


def orient(scores: np.ndarray, thematic: dict[str, np.ndarray]) -> Orientation:
    """Flip each dimension so it correlates positively with the thematic positive pole."""
    signs, notes = np.ones(scores.shape[1]), []
    for k in range(scores.shape[1]):
        correlations = {
            name: _correlation(scores[:, k], column) for name, column in thematic.items()
        }
        usable = {name: c for name, c in correlations.items() if not np.isnan(c)}
        if usable:
            best = max(usable, key=lambda name: abs(usable[name]))
            signs[k] = 1.0 if usable[best] >= 0 else -1.0
        notes.append(
            {
                "dimension": k + 1,
                "correlation_with_thematic": correlations,
                "oriented": bool(usable),
            }
        )
    return Orientation(signs, notes)


def _party_means(scores, parties, names, rng=None) -> np.ndarray:
    means = np.full((len(names), scores.shape[1]), np.nan)
    for index, name in enumerate(names):
        rows = np.flatnonzero(parties == name)
        if rng is not None:
            rows = rng.choice(rows, len(rows), replace=True)
        means[index] = scores[rows].mean(axis=0)
    return means


def estimate_party_positions(
    matrix: VoteMatrix, thematic: dict[str, np.ndarray], replicates: int, seed: int = 11
) -> dict:
    fit = fit_ideal_points(matrix.values, DIMENSIONS)
    orientation = orient(fit.scores, thematic)
    scale = fit.scores.std(axis=0)
    reference = fit.scores * orientation.signs
    parties = matrix.parties
    names = [p for p in np.unique(parties) if (parties == p).sum() >= MINIMUM_ROWS_PER_PARTY]
    draws = _bootstrap(matrix, reference, parties, names, replicates, np.random.default_rng(seed))
    summary = _summaries(fit, orientation, reference / scale, parties, names, draws, scale)
    summary["_member_scores"] = _member_scores(matrix, reference / scale)
    return summary


def _member_scores(matrix: VoteMatrix, scaled: np.ndarray) -> dict[str, list[float]]:
    """Mean dimension scores per member id across the parties the member belonged to."""
    grouped: dict[str, list[np.ndarray]] = {}
    for (member, _), row in zip(matrix.row_keys, scaled, strict=True):
        grouped.setdefault(member, []).append(row)
    return {member: np.mean(rows, axis=0).tolist() for member, rows in grouped.items()}


def _bootstrap(matrix, reference, parties, names, replicates, rng) -> np.ndarray:
    draws = np.full((replicates, len(names), reference.shape[1]), np.nan)
    columns = np.arange(matrix.values.shape[1])
    for b in range(replicates):
        picked = rng.choice(columns, len(columns), replace=True)
        try:
            replica = fit_ideal_points(matrix.values[:, picked], reference.shape[1]).scores
        except ValueError:
            continue
        draws[b] = _party_means(align_to_reference(reference, replica), parties, names, rng)
    return draws


def _summaries(fit, orientation, scaled, parties, names, draws, scale) -> dict:
    means = _party_means(scaled, parties, names)
    rows = []
    for i, name in enumerate(names):
        members = scaled[parties == name]
        rows.append(
            {
                "party": str(name),
                "n_members": int(len(members)),
                "dimensions": [
                    {
                        "dimension": k + 1,
                        "value": float(means[i, k]),
                        "ci95": [
                            float(x)
                            for x in np.nanpercentile(draws[:, i, k] / scale[k], [2.5, 97.5])
                        ],
                        "within_party_sd": float(members[:, k].std()),
                    }
                    for k in range(scaled.shape[1])
                ],
            }
        )
    return {
        "parties": rows,
        "orientation": orientation.notes,
        "explained_variance_share": [float(x) for x in fit.explained_variance_share],
        "n_rows": int(scaled.shape[0]),
        "n_roll_calls_used": int(len(fit.kept_columns)),
        "kept_columns": fit.kept_columns.tolist(),
        "bootstrap_replicates_ok": int((~np.isnan(draws[:, 0, 0])).sum()),
    }
