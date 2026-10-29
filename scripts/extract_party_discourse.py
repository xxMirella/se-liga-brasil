"""Pilot: extract discourse evidence from party documents with Gemini; dry run unless --apply.

Passages are blinded (party names masked), answered twice at temperature 0, and every quote must
exist word for word in the passage. Output stays `pending_human_review` with weight 0.
The API key is read from GEMINI_API_KEY in an env file and is never printed or stored.
"""

import argparse
import json
import sys
from pathlib import Path
from types import SimpleNamespace

from dotenv import dotenv_values

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from gemini_api.cached_generator import CachedJsonGenerator  # noqa: E402
from gemini_api.client import GeminiJsonClient  # noqa: E402
from gemini_api.request_pacer import RequestPacer  # noqa: E402
from gemini_api.response_cache import DiskResponseCache  # noqa: E402
from service.party_discourse_extraction.document_registry import discover_documents  # noqa: E402
from service.party_discourse_extraction.evidence_export import export_pending_evidence  # noqa: E402
from service.party_discourse_extraction.extraction_run import run_extraction  # noqa: E402
from service.party_discourse_extraction.extraction_store import (  # noqa: E402
    save_document_extraction,
)
from service.party_discourse_extraction.labeling import (  # noqa: E402
    sample_labeling_units,
    write_labeling_csv,
)
from service.party_discourse_extraction.passage_planning import (  # noqa: E402
    estimate_workload,
    plan_passages,
)
from service.party_discourse_extraction.prompt import (  # noqa: E402
    PROMPT_VERSION,
    build_response_schema,
    build_system_instruction,
)
from service.party_discourse_extraction.rubric_indicators import (  # noqa: E402
    indicators_by_code,
    load_rubric_indicators,
)

PARTY_MODEL_ROOT = REPOSITORY_ROOT / "data/political-orientation/party-model"
DISCOURSE_ROOT = PARTY_MODEL_ROOT / "discourse"
EXTRACTIONS_ROOT = DISCOURSE_ROOT / "extractions"
LABELING_ROOT = DISCOURSE_ROOT / "labeling"
CACHE_ROOT = DISCOURSE_ROOT / "extractions/_gemini_cache"
DEFAULT_ENV_FILES = (
    REPOSITORY_ROOT / ".env",
    Path("/home/mirella/projetos/mdqc-knowledge-center/.env"),  # hardcode-ok: .env da usuária
)
DEFAULT_MODEL = "gemini-3.5-flash"
PILOT_PARTIES = ("PT", "NOVO", "MDB")
RUN_LABELS = ("run-1", "run-2")


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parties", nargs="+", default=list(PILOT_PARTIES))
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--limit", type=int, help="process only the first N passages")
    parser.add_argument("--max-calls", type=int, default=40, help="API call budget for this run")
    parser.add_argument("--min-interval", type=float, default=6.5, help="seconds between calls")
    parser.add_argument("--env-file", type=Path, action="append")
    parser.add_argument("--apply", action="store_true", help="make real API calls")
    parser.add_argument("--labeling-set", action="store_true", help="build the human labeling set")
    parser.add_argument("--labeling-per-party", type=int, default=34)
    parser.add_argument(
        "--overwrite-labeling-set",
        action="store_true",
        help="replace an existing sheet; ids change, so never after people started labeling",
    )
    return parser.parse_args()


def read_api_key(env_files) -> str | None:
    for env_file in env_files:
        values = dotenv_values(env_file) if env_file.is_file() else {}
        key = values.get("GEMINI_API_KEY") or values.get("GOOGLE_API_KEY")
        if key:
            return key
    return None


def build_generators(arguments, api_key: str):
    pacer = RequestPacer(arguments.min_interval, arguments.max_calls)
    client = GeminiJsonClient(api_key, arguments.model, pacer)
    cache = DiskResponseCache(CACHE_ROOT)
    return {
        label: CachedJsonGenerator(client, cache, PROMPT_VERSION, label) for label in RUN_LABELS
    }, pacer


def print_plan(passages, skipped, estimate, arguments) -> None:
    print(
        json.dumps(
            {
                "mode": "apply" if arguments.apply else "dry-run",
                "model": arguments.model,
                "prompt_version": PROMPT_VERSION,
                **estimate,
                "skipped_documents": [
                    {
                        "party": item.document.political_party,
                        "sha": item.document.short_hash,
                        "reason": item.reason,
                    }
                    for item in skipped
                ],
                "free_tier_note": "RPD/TPM of the free tier are shown only in AI Studio; "
                "the run stops cleanly on 429 and resumes from the cache.",
            },
            ensure_ascii=False,
            indent=1,
        )
    )


def persist(outcome, passages, indicators, arguments) -> None:
    documents = {item.document.sha256: item.document for item in passages}
    for sha256, results in outcome.results_by_document.items():
        save_document_extraction(EXTRACTIONS_ROOT, documents[sha256], arguments.model, results)
    for political_party in arguments.parties:
        if (EXTRACTIONS_ROOT / political_party).is_dir():
            export_pending_evidence(
                EXTRACTIONS_ROOT, political_party, indicators_by_code(indicators)
            )


def run_labeling_set(passages, arguments, system_instruction, schema, codes, generators) -> None:
    if (LABELING_ROOT / "rotulagem.csv").exists() and not arguments.overwrite_labeling_set:
        sys.exit("rotulagem.csv already exists; use --overwrite-labeling-set only before labeling")
    units = sample_labeling_units(passages, arguments.parties, arguments.labeling_per_party)
    LABELING_ROOT.mkdir(parents=True, exist_ok=True)
    write_labeling_csv(units, LABELING_ROOT / "rotulagem.csv")
    internal = LABELING_ROOT / "_interno"
    internal.mkdir(exist_ok=True)
    key = {unit.unit_id: {k: v for k, v in unit.__dict__.items() if k != "text"} for unit in units}
    (internal / "chave_dos_trechos.json").write_text(json.dumps(key, ensure_ascii=False, indent=1))
    print(json.dumps({"labeling_units": len(units)}))
    if generators is None:
        return
    first_run = {RUN_LABELS[0]: generators[RUN_LABELS[0]]}
    no_document = SimpleNamespace(sha256=None)
    pseudo = [SimpleNamespace(blinded_text=unit.text, document=no_document) for unit in units]
    outcome = run_extraction(pseudo, first_run, system_instruction, schema, codes)
    predictions = {}
    for unit, result in zip(units, outcome.results_by_document[None], strict=False):
        predictions[unit.unit_id] = [
            {"indicator": i.indicator_code, "direction": i.direction, "strength": i.strength}
            for i, _ in result.labeled_items
        ]
    (internal / "ia_rotulos.json").write_text(json.dumps(predictions, ensure_ascii=False, indent=1))
    print(json.dumps({"labeling_predictions": len(predictions), "stopped": outcome.stopped_reason}))


def main():
    arguments = parse_arguments()
    indicators = load_rubric_indicators(PARTY_MODEL_ROOT / "rubric.json")
    system_instruction = build_system_instruction(indicators)
    schema = build_response_schema(indicators)
    documents = discover_documents(DISCOURSE_ROOT, REPOSITORY_ROOT, tuple(arguments.parties))
    passages, skipped = plan_passages(documents)
    selected = passages[: arguments.limit] if arguments.limit else passages
    print_plan(selected, skipped, estimate_workload(selected, system_instruction, 2), arguments)
    api_key = read_api_key(arguments.env_file or DEFAULT_ENV_FILES) if arguments.apply else None
    if arguments.apply and api_key is None:
        sys.exit("GEMINI_API_KEY not found in the env files; nothing was sent")
    generators = build_generators(arguments, api_key)[0] if arguments.apply else None
    codes = {item.code for item in indicators}
    if arguments.labeling_set:
        run_labeling_set(passages, arguments, system_instruction, schema, codes, generators)
    elif arguments.apply:
        outcome = run_extraction(selected, generators, system_instruction, schema, codes)
        persist(outcome, selected, indicators, arguments)
        print(
            json.dumps(
                {"passages_done": outcome.passages_done, "stopped_reason": outcome.stopped_reason}
            )
        )


if __name__ == "__main__":
    main()
