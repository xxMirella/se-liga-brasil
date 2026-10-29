"""Assemble party positions, cohesion and government alignment for one chamber-legislature."""

from collections import defaultdict
from pathlib import Path

import numpy as np

from service.party_vote_analysis import normalized_store as store
from service.party_vote_analysis.government_alignment import (
    government_agreement,
    leader_orientation_following,
    orientation_map,
)
from service.party_vote_analysis.legislatures import Legislature
from service.party_vote_analysis.member_matrix import build_matrix
from service.party_vote_analysis.party_metrics import cohesion_by_party, tally_votes
from service.party_vote_analysis.pca_positions import (
    MINIMUM_THEMATIC_COLUMNS,
    estimate_party_positions,
    thematic_member_scores,
)
from service.party_vote_analysis.thematic_catalog import CATALOG, ECONOMIC, SOCIOCULTURAL
from service.party_vote_analysis.thematic_scores import ItemCounts, dimension_score

ITEMS = {item.item_id: item for item in CATALOG}
MINIMUM_ROW_VOTES = 15


def load_period(directory: Path, chamber: str, legislature: Legislature):
    votes, votings, orientations = [], {}, []
    for year in range(legislature.first_year, legislature.last_year + 1):
        votes_file = store.votes_path(directory, chamber, year)
        if not votes_file.exists():
            continue
        votes.extend(store.read_votes(votes_file, chamber))
        for row in store.read_json_lines(store.votings_path(directory, chamber, year)):
            votings[row["voting_id"]] = row
        orientation_file = store.orientations_path(directory, year)
        if chamber == "camara" and orientation_file.exists():
            orientations.extend(store.read_json_lines(orientation_file))
    return votes, votings, orientations


def select_thematic_votings(votings: dict[str, dict]) -> dict[str, str]:
    """voting_id -> item_id: for each item, the roll call with the most recorded members."""
    best: dict[str, dict] = {}
    for row in votings.values():
        for item_id in row["thematic_item_ids"]:
            if item_id not in best or row["recorded_votes"] > best[item_id]["recorded_votes"]:
                best[item_id] = row
    return {row["voting_id"]: item_id for item_id, row in best.items()}


def thematic_positions(tallies, selected: dict[str, str]) -> dict[str, dict[str, dict]]:
    """party -> dimension -> score block, from the selected thematic roll calls only."""
    per_party: dict[str, dict[str, list[ItemCounts]]] = defaultdict(lambda: defaultdict(list))
    for (voting_id, party), counts in tallies.items():
        item = ITEMS.get(selected.get(voting_id, ""))
        if item is None:
            continue
        per_party[party][item.dimension].append(
            ItemCounts(item.indicator_id, item.yes_sign, counts["sim"], counts["nao"])
        )
    return {
        party: {dim: block for dim, items in dims.items() if (block := dimension_score(items))}
        for party, dims in per_party.items()
    }


def thematic_columns(matrix, selected: dict[str, str]):
    index = {voting_id: i for i, voting_id in enumerate(matrix.voting_ids)}
    result = {ECONOMIC: ([], []), SOCIOCULTURAL: ([], [])}
    for voting_id, item_id in selected.items():
        if voting_id in index:
            item = ITEMS[item_id]
            result[item.dimension][0].append(index[voting_id])
            result[item.dimension][1].append(item.yes_sign)
    return {
        dim: (np.array(cols, int), np.array(signs, float)) for dim, (cols, signs) in result.items()
    }


def build_period_report(directory: Path, chamber: str, legislature: Legislature, replicates: int):
    votes, votings, orientations = load_period(directory, chamber, legislature)
    if not votings:
        return None
    selected = select_thematic_votings(votings)
    tallies = tally_votes(votes)
    report = {
        "chamber": chamber,
        "legislature": legislature.number,
        "years": [legislature.first_year, legislature.last_year],
        "n_main_text_roll_calls": len(votings),
        "n_thematic_roll_calls": len(selected),
        "thematic_roll_calls": [_thematic_row(votings[v], ITEMS[i]) for v, i in selected.items()],
        "thematic_party_positions": thematic_positions(tallies, selected),
        "cohesion": cohesion_by_party(tallies),
    }
    report["pca"] = _pca_block(votes, votings, selected, replicates)
    report.update(_government_blocks(tallies, orientations, votings))
    return report


def _thematic_row(voting: dict, item) -> dict:
    return {
        "voting_id": voting["voting_id"],
        "item_id": item.item_id,
        "theme": item.theme,
        "indicator_id": item.indicator_id,
        "yes_sign": item.yes_sign,
        "voted_on": voting["voted_on"],
        "description": voting["description"][:200],
        "recorded_members": voting["recorded_votes"],
        "rationale": item.rationale,
    }


def _pca_block(votes, votings, selected, replicates):
    matrix = build_matrix(votes, MINIMUM_ROW_VOTES)
    if matrix.values.shape[0] < 20 or matrix.values.shape[1] < 12:
        return {
            "status": "insufficient_data",
            "n_rows": int(matrix.values.shape[0]),
            "n_roll_calls": int(matrix.values.shape[1]),
        }
    blocks = thematic_columns(matrix, selected)
    thematic = {
        dim: thematic_member_scores(matrix, cols, signs)
        for dim, (cols, signs) in blocks.items()
        if len(cols) >= MINIMUM_THEMATIC_COLUMNS
    }
    result = estimate_party_positions(matrix, thematic, replicates)
    result.pop("kept_columns")
    result["status"] = "ok"
    return result


def _government_blocks(tallies, orientations, votings) -> dict:
    if not orientations:
        return {"government_alignment": [], "leader_orientation_following": {}}
    mapping = orientation_map(orientations)
    from datetime import date

    dates = {v: date.fromisoformat(r["voted_on"]) for v, r in votings.items()}
    agreement = government_agreement(tallies, mapping, dates)
    following = leader_orientation_following(tallies, mapping)
    return {
        "government_alignment": [
            {"party": p, "government": g, "agreement": a / n, "n_roll_calls": n}
            for (p, g), (a, n) in sorted(agreement.items())
        ],
        "leader_orientation_following": {
            p: {"mean_share": float(np.mean(v)), "n_roll_calls": len(v)}
            for p, v in following.items()
        },
    }
