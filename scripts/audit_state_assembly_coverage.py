"""Audit all27 current state views without treating missing collection as an empty legislature."""

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from service.political_dashboard.contracts import STATE_NAMES  # noqa: E402
from storage.files import load_json, save_json  # noqa: E402


def inspect_state(base_url, uf):
    url = f"{base_url}/api/political-dashboard?year=2026&territory={uf}"
    try:
        with urlopen(url, timeout=30) as response:
            payload = json.load(response)
            assembly = payload["assembly"]
            return {
                "uf": uf,
                "http_status": response.status,
                "institution_code": assembly.get("institution_code"),
                "total": assembly.get("total"),
                "coverage": assembly.get("coverage"),
                **composition_metadata(assembly),
                "political_parties_sum": sum(
                    p["count"] for p in assembly.get("political_parties", [])
                ),
                "canonical_matches": assembly.get("canonical_roster_matches"),
                "source_evidence": assembly.get("evidence", []),
                "status": "published" if assembly.get("total") else "pending_collection",
            }
    except (URLError, TimeoutError) as error:
        return {"uf": uf, "status": "api_error", "error": type(error).__name__}


def composition_metadata(assembly):
    fields = (
        "aggregation_basis",
        "snapshot_on",
        "observed_on",
        "expected_seats",
        "coverage_limitation",
        "last_exercise_evidence_on",
        "reconciled_records_count",
        "observed_people_count",
    )
    return {field: assembly.get(field) for field in fields}


def attach_investigation_evidence(states, storage):
    notes = load_json(storage / "investigation-notes.json", {})
    for row in states:
        if row["status"] in {"published", "api_error"}:
            continue
        row["investigation"] = notes.get(row["uf"], {})
        failure = load_json(storage / "failures" / f"{row['uf']}.json", {})
        if failure:
            row["last_acquisition_failure"] = failure
        if row["investigation"].get("reason"):
            row["status"] = "investigated_pending_resolution"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8787")
    parser.add_argument(
        "--output", type=Path, default=Path("data/state-assembly-rosters/coverage-audit.json")
    )
    options = parser.parse_args()
    with ThreadPoolExecutor(max_workers=2) as pool:
        states = list(pool.map(lambda uf: inspect_state(options.base_url, uf), STATE_NAMES))
    attach_investigation_evidence(states, options.output.parent)
    report = {
        "schema_version": "state_assembly_coverage.v1",
        "year": 2026,
        "states": states,
        "published_states": sum(row["status"] == "published" for row in states),
        "api_error_states": sum(row["status"] == "api_error" for row in states),
        "coverage_verified": all(row["status"] != "api_error" for row in states),
    }
    save_json(options.output, report)
    print(
        json.dumps({"states_checked": len(states), "published_states": report["published_states"]})
    )


if __name__ == "__main__":
    main()
