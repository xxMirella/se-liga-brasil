"""Indicator catalog read from the approved rubric; short codes (E1, C2, G3) go to the model."""

import json
import re
from dataclasses import dataclass
from pathlib import Path

CODE_PATTERN = re.compile(r"^([ECG]\d)_")
DIMENSION_BY_GROUP = {
    "economic": "economic",
    "sociocultural": "sociocultural",
    "democratic_gate": "democratic_gate",
}


@dataclass(frozen=True)
class RubricIndicator:
    code: str
    indicator_id: str
    dimension: str
    label: str
    pole_negative: str
    pole_positive: str
    contested_direction: bool


def load_rubric_indicators(rubric_path: Path) -> tuple[RubricIndicator, ...]:
    rubric = json.loads(rubric_path.read_text())
    if not str(rubric.get("status", "")).startswith("APROVADA"):
        raise ValueError("PARTY_RUBRIC_NOT_APPROVED")
    indicators = []
    for group, dimension in DIMENSION_BY_GROUP.items():
        for entry in rubric["indicators"][group]:
            indicators.append(_indicator(entry, dimension))
    return tuple(indicators)


def _indicator(entry: dict, dimension: str) -> RubricIndicator:
    match = CODE_PATTERN.match(entry["id"])
    if match is None:
        raise ValueError("PARTY_RUBRIC_INDICATOR_CODE_INVALID")
    return RubricIndicator(
        code=match.group(1),
        indicator_id=entry["id"],
        dimension=dimension,
        label=entry["label"],
        pole_negative=entry["pole_negative_1"],
        pole_positive=entry["pole_positive_1"],
        contested_direction=bool(entry["contested_direction"]),
    )


def indicators_by_code(indicators) -> dict[str, RubricIndicator]:
    return {indicator.code: indicator for indicator in indicators}
