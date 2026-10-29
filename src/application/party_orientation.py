"""classify-political-parties: reads local files only; no network, database or catalog writes."""

import json
from collections import Counter
from pathlib import Path

from database.operations import PROJECT_ROOT
from service.party_orientation_model.batch import classify_many, parties_in_evidence, resolve_period
from service.party_orientation_model.comparison import render_comparison_report
from service.party_orientation_model.contracts import MODEL_VERSION, PartyModelContractError
from service.party_orientation_model.sensitivity import (
    SCENARIOS,
    category_changes,
    with_class_weights,
)
from service.party_orientation_model.serialization import classification_document
from service.political_dashboard.political_orientation_catalog import (
    classify_political_orientation,
)
from storage.files import write_private_bytes
from storage.party_orientation_files import (
    OUTPUT_DIRECTORY,
    ModelInputs,
    load_model_inputs,
    write_classification_documents,
)

DEFAULT_MODEL_DIRECTORY = Path("data/political-orientation/party-model")
CATALOG_FILE = Path("src/service/political_dashboard/political_orientation_catalog.json")


def _selected_parties(arguments, inputs: ModelInputs) -> list[str]:
    known = parties_in_evidence(inputs.evidence, inputs.successions)
    if arguments.all:
        names = {name.casefold(): name for name in [*_catalog_parties(), *known]}
        return sorted(names.values(), key=str.casefold)
    if not arguments.party:
        raise PartyModelContractError("PARTY_OR_ALL_REQUIRED", "use --party SIGLA[,SIGLA] ou --all")
    return [name.strip() for name in arguments.party.split(",") if name.strip()]


def _selected_periods(arguments, inputs: ModelInputs):
    if arguments.period:
        return [
            resolve_period(inputs.rubric, value.strip()) for value in arguments.period.split(",")
        ]
    if not inputs.rubric.periods:
        raise PartyModelContractError(
            "PERIOD_REQUIRED", "o rubric.json não define períodos; use --period"
        )
    return list(inputs.rubric.periods)


def _catalog_parties() -> list[str]:
    catalog = json.loads((PROJECT_ROOT / CATALOG_FILE).read_text(encoding="utf-8"))
    return sorted({row["political_party"] for row in catalog["observations"]})


def _catalog_lookup(political_party: str, year: int) -> str:
    return classify_political_orientation(political_party, year)["category"]


def _sensitivity(parties, periods, inputs: ModelInputs, base_documents: list[dict]) -> list[dict]:
    results = []
    for name, behavior_share, statements_share in SCENARIOS:
        rubric = with_class_weights(inputs.rubric, behavior_share, statements_share)
        classified = classify_many(
            parties, periods, inputs.evidence, inputs.successions, rubric, True
        )
        scenario_documents = [classification_document(item) for item in classified]
        results.append({"scenario": name, **category_changes(base_documents, scenario_documents)})
    return results


def _write_report(path: Path, documents: list[dict], sensitivity: list[dict]) -> None:
    text = render_comparison_report(
        documents, _catalog_lookup, _catalog_parties(), MODEL_VERSION, sensitivity=sensitivity
    )
    write_private_bytes(path, [(text + "\n").encode("utf-8")])


def execute_party_orientation_command(arguments) -> dict:
    model_directory = arguments.model_directory or PROJECT_ROOT / DEFAULT_MODEL_DIRECTORY
    inputs = load_model_inputs(model_directory)
    parties, periods = _selected_parties(arguments, inputs), _selected_periods(arguments, inputs)
    classifications = classify_many(
        parties,
        periods,
        inputs.evidence,
        inputs.successions,
        inputs.rubric,
        include_without_evidence=True,
    )
    documents = [classification_document(item) for item in classifications]
    files = write_classification_documents(model_directory / OUTPUT_DIRECTORY, documents)
    if arguments.comparison_report:
        _write_report(
            arguments.comparison_report,
            documents,
            _sensitivity(parties, periods, inputs, documents),
        )
    return {
        "model_version": MODEL_VERSION,
        "rubric_version": inputs.rubric.rubric_version,
        "classifications": len(documents),
        "output_directory": str(model_directory / OUTPUT_DIRECTORY),
        "evidence_files": list(inputs.evidence_files),
        "layers_without_files": list(inputs.missing_patterns),
        "evidence_files_skipped_unsupported_schema": list(inputs.skipped_files),
        "rubric_source": inputs.rubric_source,
        "categories": dict(sorted(Counter(d["category"] for d in documents).items())),
        "files_written": len(files),
    }
