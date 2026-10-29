"""File adapter of the party orientation model: reads rubric/evidence JSON, writes audit output."""

import json
from dataclasses import dataclass
from pathlib import Path

from service.party_orientation_model.contracts import (
    EVIDENCE_SCHEMA,
    EvidenceItem,
    PartyModelContractError,
    PartySuccession,
    Rubric,
)
from service.party_orientation_model.evidence import parse_evidence_document, parse_successions
from service.party_orientation_model.rubric import parse_rubric
from service.party_orientation_model.rubric_adapter import (
    adapt_proposal_to_rubric_document,
    is_proposal_document,
)
from storage.files import write_private_bytes

RUBRIC_FILE = "rubric.json"
SUCCESSIONS_FILE = "successions.json"
EVIDENCE_PATTERNS = (
    "evidence/*.json",
    "discourse/parties/*/party-discourse.json",
    "votes/party_vote_positions.json",
    "policies/parties/*/party_policy_evidence.json",
)
OUTPUT_DIRECTORY = "output"


@dataclass(frozen=True)
class ModelInputs:
    rubric: Rubric
    evidence: tuple[EvidenceItem, ...]
    successions: tuple[PartySuccession, ...]
    evidence_files: tuple[str, ...]
    missing_patterns: tuple[str, ...]
    skipped_files: tuple[str, ...] = ()
    rubric_source: str = ""


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PartyModelContractError("MODEL_INPUT_UNREADABLE", path.name) from error


def evidence_paths(model_directory: Path) -> tuple[list[Path], list[str]]:
    found, missing = [], []
    for pattern in EVIDENCE_PATTERNS:
        matches = sorted(model_directory.glob(pattern))
        found.extend(matches)
        if not matches:
            missing.append(pattern)
    return found, missing


def load_rubric(model_directory: Path) -> tuple[Rubric, str]:
    raw = _read_json(model_directory / RUBRIC_FILE)
    if is_proposal_document(raw):
        return parse_rubric(adapt_proposal_to_rubric_document(raw)), "conceptual_proposal_adapted"
    return parse_rubric(raw), "model_contract"


def _supported(paths: list[Path]) -> tuple[list[tuple[Path, dict]], list[Path]]:
    """Files in other schemas (e.g. unreviewed keyword extraction) are listed, never guessed."""
    supported, skipped = [], []
    for path in paths:
        document = _read_json(path)
        if document.get("schema_version") == EVIDENCE_SCHEMA:
            supported.append((path, document))
        else:
            skipped.append(path)
    return supported, skipped


def load_model_inputs(model_directory: Path) -> ModelInputs:
    rubric, rubric_source = load_rubric(model_directory)
    paths, missing = evidence_paths(model_directory)
    supported, skipped = _supported(paths)
    evidence = tuple(
        item for _, document in supported for item in parse_evidence_document(document, rubric)
    )
    identifiers = [item.evidence_id for item in evidence]
    if len(set(identifiers)) != len(identifiers):
        raise PartyModelContractError("EVIDENCE_ID_DUPLICATED_ACROSS_FILES")
    succession_path = model_directory / SUCCESSIONS_FILE
    successions = parse_successions(_read_json(succession_path)) if succession_path.exists() else ()
    return ModelInputs(
        rubric,
        evidence,
        successions,
        tuple(str(path.relative_to(model_directory)) for path, _ in supported),
        tuple(missing),
        tuple(str(path.relative_to(model_directory)) for path in skipped),
        rubric_source,
    )


def serialize_document(document: dict) -> bytes:
    text = json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True)
    return (text + "\n").encode("utf-8")


def write_classification_documents(output_directory: Path, documents: list[dict]) -> list[str]:
    """One file per party and period plus an index; identical inputs give identical bytes."""
    index = []
    for document in documents:
        relative = f"{document['political_party_id']}/{document['period']['period_id']}.json"
        write_private_bytes(output_directory / relative, [serialize_document(document)])
        index.append(
            {
                "file": relative,
                "political_party": document["political_party"],
                "period_id": document["period"]["period_id"],
                "category": document["category"],
                "overall_score": document["overall_score"],
                "confidence_label": document["confidence_label"],
                "input_digest_sha256": document["input_digest_sha256"],
            }
        )
    index.sort(key=lambda entry: entry["file"])
    write_private_bytes(
        output_directory / "index.json",
        [
            serialize_document(
                {
                    "model_version": documents[0]["model_version"] if documents else None,
                    "classifications": index,
                }
            )
        ],
    )
    return [entry["file"] for entry in index]
