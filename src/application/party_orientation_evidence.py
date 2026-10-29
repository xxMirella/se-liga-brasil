"""build-party-orientation-evidence: converts collected layers to evidence files; local only."""

import json
from datetime import date
from pathlib import Path

from database.operations import PROJECT_ROOT
from service.party_orientation_evidence.discourse import (
    discourse_conversion_notes,
    self_declaration_records,
)
from service.party_orientation_evidence.expert import (
    bolognesi_records,
    expert_conversion_notes,
    zucco_records,
)
from service.party_orientation_evidence.policies import legal_act_records, policy_conversion_notes
from service.party_orientation_evidence.records import evidence_document
from service.party_orientation_evidence.votes import (
    procedural_voting_ids,
    thematic_vote_records,
    vote_conversion_notes,
)
from service.party_orientation_model.contracts import Rubric
from storage.party_orientation_evidence_files import (
    DISCOURSE_REVIEW_FILE,
    LEGAL_ACTS_FILE,
    LEGAL_ACTS_VERIFIED_FILE,
    VOTE_POSITIONS_FILE,
    read_discourse_documents,
    read_json,
    read_zucco_estimates,
    thematic_tallies,
    vote_source_urls,
    write_evidence_documents,
)
from storage.party_orientation_files import load_rubric

DEFAULT_MODEL_DIRECTORY = Path("data/political-orientation/party-model")
CATALOG_FILE = Path("src/service/political_dashboard/political_orientation_catalog.json")


def votes_document(model_directory: Path, rubric: Rubric, generated_on: date) -> dict:
    urls = vote_source_urls(model_directory)
    records = []
    blocks = read_json(model_directory / VOTE_POSITIONS_FILE)["periods"]
    for block in blocks:
        records.extend(
            thematic_vote_records(
                block,
                thematic_tallies(model_directory, block),
                lambda chamber, year: urls[(chamber, year)],
                rubric,
            )
        )
    notes = vote_conversion_notes(procedural_voting_ids(blocks))
    return evidence_document("votes", records, notes, generated_on)


def policies_document(model_directory: Path, rubric: Rubric, generated_on: date) -> dict:
    acts = read_json(model_directory / LEGAL_ACTS_FILE)
    verification = {row["id"]: row for row in read_json(model_directory / LEGAL_ACTS_VERIFIED_FILE)}
    records, skipped = legal_act_records(acts, verification, rubric)
    return evidence_document(
        "implemented_policies", records, policy_conversion_notes(skipped), generated_on
    )


def expert_document(model_directory: Path, generated_on: date) -> dict:
    catalog = json.loads((PROJECT_ROOT / CATALOG_FILE).read_text(encoding="utf-8"))
    records = bolognesi_records(catalog["observations"])
    records += zucco_records(read_zucco_estimates(model_directory))
    return evidence_document("expert_survey", records, expert_conversion_notes(), generated_on)


def discourse_document(model_directory: Path, generated_on: date) -> dict:
    review_path = model_directory / DISCOURSE_REVIEW_FILE
    reviews = read_json(review_path)["reviews"] if review_path.exists() else []
    records = self_declaration_records(reviews, read_discourse_documents(model_directory))
    return evidence_document("discourse", records, discourse_conversion_notes(), generated_on)


def execute_party_orientation_evidence_command(arguments) -> dict:
    model_directory = arguments.model_directory or PROJECT_ROOT / DEFAULT_MODEL_DIRECTORY
    rubric = load_rubric(model_directory)[0]
    generated_on = date.today()
    documents = [
        votes_document(model_directory, rubric, generated_on),
        policies_document(model_directory, rubric, generated_on),
        expert_document(model_directory, generated_on),
        discourse_document(model_directory, generated_on),
    ]
    files = write_evidence_documents(model_directory, documents, rubric)
    return {
        "rubric_version": rubric.rubric_version,
        "files_written": files,
        "evidence_by_layer": {d["layer_name"]: len(d["evidence"]) for d in documents},
    }
