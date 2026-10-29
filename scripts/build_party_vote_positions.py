"""Compute party positions from the normalized roll calls and write party_vote_positions.json.

Usage: .venv/bin/python scripts/build_party_vote_positions.py [--replicates 100] [--chamber camara]
"""

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from service.party_vote_analysis import normalized_store as store  # noqa: E402
from service.party_vote_analysis.legislatures import LEGISLATURES  # noqa: E402
from service.party_vote_analysis.orientation_continuity import (  # noqa: E402
    government_axis_check,
    propagate_orientation,
)  # noqa: E402
from service.party_vote_analysis.paths import NORMALIZED_DIRECTORY, VOTES_DIRECTORY  # noqa: E402
from service.party_vote_analysis.positions_report import build_period_report  # noqa: E402
from service.party_vote_analysis.thematic_catalog import EXCLUDED_THEMES  # noqa: E402


def coverage_by_year() -> dict:
    """Per year and chamber: main-text roll calls kept, member votes, and raw availability."""
    manifest = json.loads((VOTES_DIRECTORY / "raw" / "manifest.json").read_text(encoding="utf-8"))
    availability = {e["arquivo"]: e for e in manifest["arquivos"]}
    coverage = {}
    for year in range(1991, 2027):
        coverage[year] = {}
        for chamber, raw_name in (
            ("camara", f"camara/votacoesVotos-{year}.csv"),
            ("senado", f"senado/votacao-{year}.json"),
        ):
            path = store.votings_path(NORMALIZED_DIRECTORY, chamber, year)
            rows = list(store.read_json_lines(path)) if path.exists() else []
            entry = availability.get(raw_name, {})
            coverage[year][chamber] = {
                "raw_available": "http_status" not in entry and bool(entry),
                "main_text_roll_calls": len(rows),
                "member_votes": sum(r["recorded_votes"] for r in rows),
                "thematic_roll_calls": sum(1 for r in rows if r["thematic_item_ids"]),
            }
    return coverage


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--replicates", type=int, default=100)
    parser.add_argument("--chamber", choices=["camara", "senado"], action="append")
    arguments = parser.parse_args()
    reports = []
    for chamber in arguments.chamber or ["camara", "senado"]:
        for legislature in LEGISLATURES:
            started = time.time()
            report = build_period_report(
                NORMALIZED_DIRECTORY, chamber, legislature, arguments.replicates
            )
            if report:
                reports.append(report)
            print(
                chamber,
                legislature.number,
                bool(report),
                round(time.time() - started),
                "s",
                flush=True,
            )
    for chamber in {r["chamber"] for r in reports}:
        propagate_orientation([r for r in reports if r["chamber"] == chamber])
    for report in reports:
        if report["pca"].get("status") == "ok":
            report["pca"]["first_dimension_vs_government_agreement"] = government_axis_check(report)
        report["pca"].pop("_member_scores", None)
    document = {
        "generated_on": datetime.now(UTC).date().isoformat(),
        "methodology": "docs/partidos-votacoes-metodologia.md",
        "bootstrap_replicates": arguments.replicates,
        "coverage_by_year": coverage_by_year(),
        "excluded_themes": EXCLUDED_THEMES,
        "periods": reports,
    }
    output = VOTES_DIRECTORY / "party_vote_positions.json"
    output.write_text(json.dumps(document, ensure_ascii=False, indent=1), encoding="utf-8")
    print("written", output)


if __name__ == "__main__":
    main()
