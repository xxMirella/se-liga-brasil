"""Turns archived documents into blinded passages ready for the model, and sizes the workload."""

from dataclasses import dataclass

from service.party_discourse_extraction.blinding import blind_text
from service.party_discourse_extraction.document_registry import PartyDocument
from service.party_discourse_extraction.document_text import DocumentText, load_document_text
from service.party_discourse_extraction.relevance import assess_relevance
from service.party_discourse_extraction.segmentation import Segment, segment_document

CHARACTERS_PER_TOKEN = 3.5  # conservative for Portuguese; only used for the dry-run estimate


@dataclass(frozen=True)
class PlannedPassage:
    document: PartyDocument
    text_origin: str
    segment: Segment
    blinded_text: str
    masked_counts: dict[str, int]
    indicator_hints: tuple[str, ...]


@dataclass(frozen=True)
class SkippedDocument:
    document: PartyDocument
    reason: str


def _passages_of(document: PartyDocument, loaded: DocumentText) -> list[PlannedPassage]:
    passages = []
    document_key = f"{document.political_party}-{document.short_hash}"
    for segment in segment_document(loaded.text, document_key):
        blinded = blind_text(segment.text, document.political_party)
        relevance = assess_relevance(blinded.text)
        if relevance.is_relevant:
            passages.append(
                PlannedPassage(
                    document,
                    loaded.origin,
                    segment,
                    blinded.text,
                    blinded.masked_counts,
                    relevance.indicator_hints,
                )
            )
    return passages


def plan_passages(documents, loader=load_document_text):
    passages, skipped = [], []
    for document in documents:
        loaded = loader(document.path, document.ocr_text_path)
        if loaded is None:
            skipped.append(SkippedDocument(document, "no_text_layer_and_no_ocr_yet"))
            continue
        passages.extend(_passages_of(document, loaded))
    return passages, skipped


def estimate_workload(passages, system_instruction: str, runs: int) -> dict:
    system_tokens = round(len(system_instruction) / CHARACTERS_PER_TOKEN)
    passage_tokens = sum(round(len(item.blinded_text) / CHARACTERS_PER_TOKEN) for item in passages)
    return {
        "passages": len(passages),
        "calls": len(passages) * runs,
        "estimated_input_tokens": (passage_tokens + system_tokens * len(passages)) * runs,
        "system_instruction_tokens": system_tokens,
    }
