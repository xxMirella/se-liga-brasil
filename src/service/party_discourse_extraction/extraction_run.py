"""Drives the extraction over many passages and stops cleanly when a quota or budget ends."""

from collections import defaultdict
from dataclasses import dataclass, field

from gemini_api.client import GeminiApiError
from gemini_api.request_pacer import CallBudgetExhaustedError
from service.party_discourse_extraction.passage_extraction import PassageResult, extract_passage


@dataclass
class RunOutcome:
    results_by_document: dict[str, list[PassageResult]] = field(
        default_factory=lambda: defaultdict(list)
    )
    stopped_reason: str | None = None
    passages_done: int = 0


def run_extraction(passages, generators, system_instruction, response_schema, valid_codes):
    """Partial results are kept: answers already paid for sit in the cache for the next run."""
    outcome = RunOutcome()
    try:
        for passage in passages:
            result = extract_passage(
                passage, generators, system_instruction, response_schema, valid_codes
            )
            outcome.results_by_document[passage.document.sha256].append(result)
            outcome.passages_done += 1
    except (CallBudgetExhaustedError, GeminiApiError) as error:
        outcome.stopped_reason = str(error)
    return outcome
