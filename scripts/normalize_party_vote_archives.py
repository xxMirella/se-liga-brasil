"""Normalize the raw roll-call archives into compact per-year files (main-text votes only).

Large Chamber vote files (>50 MB) are read once in streaming mode and their bytes are
released afterwards (URL + sha256 stay in the manifest). Usage:
  .venv/bin/python scripts/normalize_party_vote_archives.py [--first-year Y --last-year Y]
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from crawlers.camara import nominal_vote_normalization as camara  # noqa: E402
from crawlers.senado import nominal_vote_normalization as senado  # noqa: E402
from service.party_vote_analysis import normalized_store as store  # noqa: E402
from service.party_vote_analysis.paths import NORMALIZED_DIRECTORY, RAW_DIRECTORY  # noqa: E402
from service.party_vote_analysis.thematic_matching import match_thematic_items  # noqa: E402
from storage.polite_archive import PoliteArchive  # noqa: E402


def voting_row(voting, extra_votes_count: int) -> dict:
    items = match_thematic_items(voting.chamber, voting.propositions)
    return {
        "voting_id": voting.voting_id,
        "voted_on": voting.voted_on.isoformat(),
        "description": voting.description,
        "source_file": voting.source_file,
        "propositions": [[p.kind, p.number, p.year, p.summary] for p in voting.propositions],
        "thematic_item_ids": sorted(item.item_id for item in items),
        "recorded_votes": extra_votes_count,
    }


def normalize_camara_year(archive: PoliteArchive, year: int) -> dict | None:
    raw = RAW_DIRECTORY / "camara"
    votes_name = f"camara/votacoesVotos-{year}.csv"
    if archive.entries.get(votes_name, {}).get("http_status") or votes_name not in archive.entries:
        return None
    if archive.is_processed_large_file(votes_name):
        return {"skipped": "already processed"}
    votings = camara.plenary_main_text_votings(
        raw / f"votacoes-{year}.csv", raw / f"votacoesProposicoes-{year}.csv"
    )
    counts: dict[str, int] = {}

    def counted():
        for vote in camara.stream_votes(raw / f"votacoesVotos-{year}.csv", votings):
            counts[vote.voting_id] = counts.get(vote.voting_id, 0) + 1
            yield vote

    total = store.write_votes(store.votes_path(NORMALIZED_DIRECTORY, "camara", year), counted())
    kept = [votings[i] for i in votings if counts.get(i, 0) > 0]
    store.write_json_lines(
        store.votings_path(NORMALIZED_DIRECTORY, "camara", year),
        (voting_row(v, counts[v.voting_id]) for v in kept),
    )
    orientation_file = raw / f"votacoesOrientacoes-{year}.csv"
    if orientation_file.exists():
        store.write_json_lines(
            store.orientations_path(NORMALIZED_DIRECTORY, year),
            (
                store.orientation_row(o)
                for o in camara.stream_orientations(orientation_file, {v.voting_id for v in kept})
            ),
        )
    archive.release(votes_name)
    return {"votings": len(kept), "vote_rows": total}


def normalize_senado_year(archive: PoliteArchive, year: int) -> dict | None:
    name = f"senado/votacao-{year}.json"
    if name not in archive.entries or archive.entries[name].get("http_status"):
        return None
    pairs = list(senado.read_substantive_votings(RAW_DIRECTORY / name))
    votes = (vote for _, group in pairs for vote in group)
    total = store.write_votes(store.votes_path(NORMALIZED_DIRECTORY, "senado", year), votes)
    store.write_json_lines(
        store.votings_path(NORMALIZED_DIRECTORY, "senado", year),
        (voting_row(v, len(g)) for v, g in pairs),
    )
    return {"votings": len(pairs), "vote_rows": total}


def merge_senate_manifest() -> None:
    senate_path = RAW_DIRECTORY / "manifest-senado.json"
    main_path = RAW_DIRECTORY / "manifest.json"
    if not senate_path.exists():
        return
    main = json.loads(main_path.read_text(encoding="utf-8"))
    senate = json.loads(senate_path.read_text(encoding="utf-8"))
    known = {e["arquivo"] for e in main["arquivos"]}
    main["arquivos"] += [e for e in senate["arquivos"] if e["arquivo"] not in known]
    main_path.write_text(json.dumps(main, ensure_ascii=False, indent=1), encoding="utf-8")
    senate_path.unlink()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--first-year", type=int, default=1991)
    parser.add_argument("--last-year", type=int, default=2026)
    arguments = parser.parse_args()
    merge_senate_manifest()
    archive = PoliteArchive(RAW_DIRECTORY)
    summary = {}
    for year in range(arguments.first_year, arguments.last_year + 1):
        summary[year] = {
            "camara": normalize_camara_year(archive, year),
            "senado": normalize_senado_year(archive, year),
        }
        print(year, summary[year], flush=True)
    archive.close()
    out = NORMALIZED_DIRECTORY / "normalization-summary.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
