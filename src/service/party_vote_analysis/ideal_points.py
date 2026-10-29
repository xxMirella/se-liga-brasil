"""Ideal points by iterative (EM) principal components of a member x roll-call matrix.

Entries are +1 (yes), -1 (no) and NaN (absent, abstention, obstruction, other). This is a
transparent PCA, not W-NOMINATE: it has no utility model and no error term. Pure numerics:
no network, no database.
"""

from dataclasses import dataclass

import numpy as np

MINIMUM_MINORITY_SHARE = 0.025
MINIMUM_VOTERS_PER_ROLL_CALL = 10
EM_ITERATIONS = 8


@dataclass(frozen=True)
class IdealPointFit:
    scores: np.ndarray  # rows x dimensions
    explained_variance_share: np.ndarray  # dimensions
    kept_columns: np.ndarray  # indexes of roll calls used


def informative_columns(matrix: np.ndarray) -> np.ndarray:
    """Indexes of roll calls with enough voters and a non-lopsided split (Poole & Rosenthal)."""
    yes = np.nansum(matrix == 1, axis=0)
    no = np.nansum(matrix == -1, axis=0)
    voters = yes + no
    minority = np.minimum(yes, no)
    with np.errstate(divide="ignore", invalid="ignore"):
        share = np.where(voters > 0, minority / voters, 0.0)
    keep = (voters >= MINIMUM_VOTERS_PER_ROLL_CALL) & (share >= MINIMUM_MINORITY_SHARE)
    return np.flatnonzero(keep)


def _fill_by_rank(centered: np.ndarray, missing: np.ndarray, dimensions: int):
    filled = np.where(missing, 0.0, centered)
    for _ in range(EM_ITERATIONS):
        left, spectrum, right = np.linalg.svd(filled, full_matrices=False)
        rebuilt = (left[:, :dimensions] * spectrum[:dimensions]) @ right[:dimensions]
        filled = np.where(missing, rebuilt, centered)
    return left, spectrum


def fit_ideal_points(matrix: np.ndarray, dimensions: int = 2) -> IdealPointFit:
    if (
        matrix.ndim != 2
        or isinstance(dimensions, bool)
        or not isinstance(dimensions, int)
        or dimensions < 1
    ):
        raise ValueError("matrix must be two-dimensional and dimensions a positive integer")
    if not np.all(np.isnan(matrix) | (matrix == 1) | (matrix == -1)):
        raise ValueError("matrix accepts only yes (+1), no (-1) and missing (NaN)")
    columns = informative_columns(matrix)
    if len(columns) < dimensions + 1 or matrix.shape[0] < dimensions + 1:
        raise ValueError("not enough informative roll calls or members")
    subset = matrix[:, columns]
    missing = np.isnan(subset)
    column_means = np.nanmean(np.where(missing, np.nan, subset), axis=0)
    centered = np.where(missing, 0.0, subset - column_means)
    left, spectrum = _fill_by_rank(centered, missing, dimensions)
    variance = spectrum**2
    scores = left[:, :dimensions] * spectrum[:dimensions]
    scores[np.all(missing, axis=1)] = np.nan
    return IdealPointFit(
        scores=scores,
        explained_variance_share=variance[:dimensions] / variance.sum(),
        kept_columns=columns,
    )


def align_to_reference(reference: np.ndarray, candidate: np.ndarray) -> np.ndarray:
    """Match dimensions and signs of a replicate to the reference by correlation."""
    dimensions = reference.shape[1]
    correlation = np.corrcoef(reference.T, candidate.T)[:dimensions, dimensions:]
    aligned = np.empty_like(reference)
    used: set[int] = set()
    for target in range(dimensions):
        order = np.argsort(-np.abs(correlation[target]))
        source = next(index for index in order if index not in used)
        used.add(int(source))
        aligned[:, target] = candidate[:, source] * np.sign(correlation[target, source] or 1.0)
    return aligned
