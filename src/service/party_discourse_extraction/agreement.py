"""Cohen's kappa between two labelers, or between a person and the model."""

from collections import Counter


def cohen_kappa(first: list[str], second: list[str]) -> float | None:
    """None when there is nothing to compare or chance agreement is already perfect."""
    if len(first) != len(second) or not first:
        return None
    total = len(first)
    observed = sum(a == b for a, b in zip(first, second, strict=True)) / total
    first_counts, second_counts = Counter(first), Counter(second)
    expected = sum(first_counts[label] * second_counts[label] for label in first_counts) / total**2
    if expected == 1:
        return None
    return round((observed - expected) / (1 - expected), 3)


def agreement_summary(first: list[str], second: list[str]) -> dict:
    total = len(first)
    matches = sum(a == b for a, b in zip(first, second, strict=True))
    return {
        "items": total,
        "raw_agreement": round(matches / total, 3) if total else None,
        "cohen_kappa": cohen_kappa(first, second),
    }
