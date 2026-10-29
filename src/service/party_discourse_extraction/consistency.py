"""Compares two independent runs over the same passage; disagreement goes to priority review."""

from dataclasses import dataclass

from service.party_discourse_extraction.validation import ExtractedItem, normalize_for_matching

SIMILARITY_THRESHOLD = 0.6


@dataclass(frozen=True)
class ConsistencyReport:
    agree: int
    direction_conflict: int
    only_first_run: int
    only_second_run: int

    @property
    def agreement_rate(self) -> float | None:
        total = self.agree + self.direction_conflict + self.only_first_run + self.only_second_run
        return None if total == 0 else round(self.agree / total, 3)


def _token_overlap(first: str, second: str) -> float:
    left, right = set(first.split()), set(second.split())
    return len(left & right) / len(left | right) if left | right else 0.0


def _same_statement(first: ExtractedItem, second: ExtractedItem) -> bool:
    if first.indicator_code != second.indicator_code:
        return False
    left, right = normalize_for_matching(first.quote), normalize_for_matching(second.quote)
    return left in right or right in left or _token_overlap(left, right) >= SIMILARITY_THRESHOLD


def label_consistency(first_run, second_run):
    """Label each first-run item agree | direction_conflict | single_run, and count the rest."""
    unmatched = list(second_run)
    labeled, agree, conflict = [], 0, 0
    for item in first_run:
        match = next((other for other in unmatched if _same_statement(item, other)), None)
        if match is None:
            labeled.append((item, "single_run"))
            continue
        unmatched.remove(match)
        same_direction = item.direction == match.direction
        agree, conflict = agree + same_direction, conflict + (not same_direction)
        labeled.append((item, "agree" if same_direction else "direction_conflict"))
    only_first = sum(1 for _, status in labeled if status == "single_run")
    return labeled, ConsistencyReport(agree, conflict, only_first, len(unmatched))
