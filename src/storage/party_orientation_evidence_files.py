"""File adapter of the evidence conversion: reads the collected layers, writes validated evidence.

The collectors' own files (`votes/party_vote_positions.json`, `policies/...`, `discourse/...`) are
never overwritten; converted evidence goes to `evidence/<layer>.json`.
"""

import csv
import json
from collections import defaultdict
from pathlib import Path

from service.party_orientation_model.contracts import (
    PartyModelContractError,
    Rubric,
    normalize_party_key,
)
from service.party_orientation_model.evidence import parse_evidence_document
from service.party_vote_analysis import normalized_store
from service.party_vote_analysis.choices import Choice
from storage.files import write_private_bytes
from storage.party_orientation_files import serialize_document

EVIDENCE_DIRECTORY = "evidence"
VOTE_POSITIONS_FILE = "votes/party_vote_positions.json"
VOTE_MANIFEST_FILE = "votes/raw/manifest.json"
NORMALIZED_VOTES_DIRECTORY = "votes/normalized"
LEGAL_ACTS_FILE = "policies/curated/legal_acts.json"
LEGAL_ACTS_VERIFIED_FILE = "policies/derived/legal_acts_verified.json"
ZUCCO_ESTIMATES_FILE = "../party-sources-1992-1994/power-zucco-2009-party-estimates.csv"
DISCOURSE_REVIEW_FILE = "evidence/curated/discourse-self-declarations.json"
DISCOURSE_PARTIES_PATTERN = "discourse/parties/*/party-discourse.json"
VOTE_FILE_TYPES = {"camara": "votacoesVotos", "senado": "senado_votacao"}


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PartyModelContractError("MODEL_INPUT_UNREADABLE", path.name) from error


def vote_source_urls(model_directory: Path) -> dict[tuple[str, int], str]:
    """(chamber, year) -> URL of the official file the votes of that year were read from."""
    manifest = read_json(model_directory / VOTE_MANIFEST_FILE)
    wanted = {value: chamber for chamber, value in VOTE_FILE_TYPES.items()}
    return {
        (wanted[entry["tipo"]], entry["ano"]): entry["url"]
        for entry in manifest["arquivos"]
        if entry["tipo"] in wanted
    }


def thematic_tallies(model_directory: Path, block: dict) -> dict[str, dict[str, dict[str, int]]]:
    """voting_id -> party -> {'sim','nao'}; streams each year file once, only the votings."""
    wanted: dict[int, set[str]] = defaultdict(set)
    for roll_call in block["thematic_roll_calls"]:
        wanted[int(roll_call["voted_on"][:4])].add(roll_call["voting_id"])
    tallies: dict[str, dict[str, dict[str, int]]] = {}
    directory = model_directory / NORMALIZED_VOTES_DIRECTORY
    for year, voting_ids in sorted(wanted.items()):
        path = normalized_store.votes_path(directory, block["chamber"], year)
        for vote in normalized_store.read_votes(path, block["chamber"]):
            if vote.voting_id in voting_ids and vote.choice in (Choice.YES, Choice.NO):
                party = tallies.setdefault(vote.voting_id, {}).setdefault(
                    vote.party_at_vote, {"sim": 0, "nao": 0}
                )
                party[vote.choice.value] += 1
    return tallies


def read_zucco_estimates(model_directory: Path) -> dict[str, dict[int, float]]:
    estimates: dict[str, dict[int, float]] = {}
    path = (model_directory / ZUCCO_ESTIMATES_FILE).resolve()
    with path.open(encoding="utf-8", newline="") as source:
        for row in csv.DictReader(source):
            label = row[""]
            for column, value in row.items():
                if column.startswith("party.estimates.") and value not in ("", "NA"):
                    estimates.setdefault(label, {})[int(column.rsplit(".", 1)[1])] = float(value)
    return estimates


def read_discourse_documents(model_directory: Path) -> dict[str, dict]:
    documents = {}
    for path in sorted(model_directory.glob(DISCOURSE_PARTIES_PATTERN)):
        document = read_json(path)
        documents[normalize_party_key(document["partido"])] = document
    return documents


def write_evidence_documents(model_directory: Path, documents: list[dict], rubric: Rubric):
    """Validate each document against the contract before writing; identical input, same bytes."""
    written = []
    for document in documents:
        parse_evidence_document(document, rubric)
        relative = f"{EVIDENCE_DIRECTORY}/{document['layer_name']}.json"
        write_private_bytes(model_directory / relative, [serialize_document(document)])
        written.append(relative)
    return written
