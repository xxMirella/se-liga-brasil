"""Party score on thematic roll calls: share of yes/no votes on the indicator's positive pole.

Per roll call the score is 2*share_toward_positive_pole - 1 (rubric aggregation rule), the
dimension score averages roll calls inside each indicator and then the indicators, and the
uncertainty comes from a bootstrap that resamples roll calls and re-draws each party's
yes/no split from a binomial around the observed split (finite number of members).
"""

from dataclasses import dataclass

import numpy as np

MINIMUM_VOTERS = 3
BOOTSTRAP_REPLICATES = 1000


@dataclass(frozen=True)
class ItemCounts:
    indicator_id: str
    yes_sign: int
    yes: int
    no: int


def pole_score(yes: np.ndarray, no: np.ndarray, yes_sign: np.ndarray) -> np.ndarray:
    total = yes + no
    with np.errstate(divide="ignore", invalid="ignore"):
        share_yes = np.where(total > 0, yes / total, np.nan)
    pole_share = np.where(yes_sign > 0, share_yes, 1 - share_yes)
    return 2 * pole_share - 1


def _mean_by_indicator(scores: np.ndarray, groups: np.ndarray) -> float:
    means = [
        np.nanmean(scores[groups == g])
        for g in np.unique(groups)
        if not np.all(np.isnan(scores[groups == g]))
    ]
    return float(np.mean(means)) if means else float("nan")


def dimension_score(items: list[ItemCounts], seed: int = 7) -> dict | None:
    usable = [item for item in items if item.yes + item.no >= MINIMUM_VOTERS]
    if not usable:
        return None
    yes = np.array([i.yes for i in usable], float)
    no = np.array([i.no for i in usable], float)
    sign = np.array([i.yes_sign for i in usable])
    groups = np.array([i.indicator_id for i in usable])
    value = _mean_by_indicator(pole_score(yes, no, sign), groups)
    low, high = _bootstrap_interval(yes, no, sign, groups, np.random.default_rng(seed))
    return {
        "value": value,
        "ci95": [low, high],
        "n_votings": len(usable),
        "n_indicators": int(len(np.unique(groups))),
    }


def _bootstrap_interval(yes, no, sign, groups, rng):
    size = len(yes)
    totals = (yes + no).astype(int)
    draws = []
    for _ in range(BOOTSTRAP_REPLICATES):
        picked = rng.integers(0, size, size)
        simulated_yes = rng.binomial(totals[picked], yes[picked] / totals[picked])
        score = pole_score(simulated_yes, totals[picked] - simulated_yes, sign[picked])
        draws.append(_mean_by_indicator(score, groups[picked]))
    low, high = np.nanpercentile(draws, [2.5, 97.5])
    return float(low), float(high)
