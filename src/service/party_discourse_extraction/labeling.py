"""Builds the human labeling set: short blinded passages, stratified by party and indicator hint."""

import csv
import random
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from service.party_discourse_extraction.relevance import assess_relevance

MIN_UNIT_WORDS = 25
MAX_UNIT_CHARACTERS = 1200
CSV_COLUMNS = (
    "id_do_trecho",
    "texto",
    "indicador_sugerido_pela_ia",
    "indicador",
    "direcao",
    "forca",
    "tipo",
    "comentario",
)
CSV_DELIMITER = ";"  # Excel in pt-BR splits columns on ';'; Google Sheets detects it on import


@dataclass(frozen=True)
class LabelingUnit:
    unit_id: str
    political_party: str
    document_sha256: str
    segment_id: str
    text: str
    indicator_hint: str


def candidate_units(passage) -> list[tuple[str, str]]:
    """(text, first indicator hint) for each short paragraph of a planned passage."""
    units = []
    for paragraph in re.split(r"\n\s*\n", passage.blinded_text):
        text = " ".join(paragraph.split())
        relevance = assess_relevance(text)
        long_enough = len(text.split()) >= MIN_UNIT_WORDS
        if relevance.is_relevant and long_enough and len(text) <= MAX_UNIT_CHARACTERS:
            units.append((text, relevance.indicator_hints[0]))
    return units


def _strata_of(passages, political_party: str) -> dict[str, list[tuple]]:
    strata: dict[str, list[tuple]] = defaultdict(list)
    for passage in passages:
        if passage.document.political_party != political_party:
            continue
        for text, hint in candidate_units(passage):
            strata[hint].append((passage, text))
    return strata


def _round_robin(strata: dict[str, list[tuple]], quota: int, rng: random.Random) -> list[tuple]:
    pools = {hint: rng.sample(items, len(items)) for hint, items in sorted(strata.items())}
    chosen: list[tuple] = []
    while len(chosen) < quota and any(pools.values()):
        for hint, pool in pools.items():
            if pool and len(chosen) < quota:
                passage, text = pool.pop()
                chosen.append((passage, text, hint))
    return chosen


def sample_labeling_units(passages, parties, per_party: int, seed: int = 20261029):
    rng = random.Random(seed)
    sampled = []
    for political_party in parties:
        sampled.extend(_round_robin(_strata_of(passages, political_party), per_party, rng))
    rng.shuffle(sampled)  # neutral ids: the order must not reveal the party
    return [
        LabelingUnit(
            f"T{number:03d}",
            passage.document.political_party,
            passage.document.sha256,
            passage.segment.segment_id,
            text,
            hint,
        )
        for number, (passage, text, hint) in enumerate(sampled, start=1)
    ]


def write_labeling_csv(units: list[LabelingUnit], path: Path) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, delimiter=CSV_DELIMITER)
        writer.writerow(CSV_COLUMNS)
        for unit in units:
            writer.writerow([unit.unit_id, unit.text, "", "", "", "", "", ""])
