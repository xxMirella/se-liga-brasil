"""Runs the model twice over one blinded passage and validates every answer deterministically."""

from dataclasses import dataclass

from service.party_discourse_extraction.consistency import ConsistencyReport, label_consistency
from service.party_discourse_extraction.passage_planning import PlannedPassage
from service.party_discourse_extraction.prompt import build_user_text
from service.party_discourse_extraction.validation import (
    DiscardedItem,
    ExtractedItem,
    validate_response,
)


@dataclass(frozen=True)
class PassageResult:
    passage: PlannedPassage
    labeled_items: list[tuple[ExtractedItem, str]]
    second_run_items: list[ExtractedItem]
    discarded: list[tuple[str, DiscardedItem]]  # (run label, item)
    consistency: ConsistencyReport
    usage: list[dict]


def extract_passage(passage, generators, system_instruction, response_schema, valid_codes):
    """`generators` maps a run label to its generator: two runs, or one for the labeling set."""
    accepted_by_run, discarded, usage = [], [], []
    for run_label, generator in generators.items():
        generated = generator.generate_json(
            system_instruction, build_user_text(passage.blinded_text), response_schema
        )
        accepted, rejected = validate_response(generated.text, passage.blinded_text, valid_codes)
        accepted_by_run.append(accepted)
        discarded.extend((run_label, item) for item in rejected)
        usage.append(generated.usage)
    if len(accepted_by_run) == 1:  # labeling set: one run, nothing to compare
        first = accepted_by_run[0]
        labeled = [(item, "single_run") for item in first]
        report = ConsistencyReport(0, 0, len(first), 0)
        return PassageResult(passage, labeled, [], discarded, report, usage)
    labeled, report = label_consistency(*accepted_by_run)
    return PassageResult(passage, labeled, accepted_by_run[1], discarded, report, usage)
