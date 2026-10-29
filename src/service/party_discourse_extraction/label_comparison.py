"""Reads filled labeling sheets and compares labelers (and the model) with Cohen's kappa."""

import csv
from pathlib import Path

from service.party_discourse_extraction.agreement import agreement_summary
from service.party_discourse_extraction.labeling import CSV_DELIMITER

NO_LABEL = "nenhum"


def read_labels(path: Path) -> dict[str, dict]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = csv.DictReader(stream, delimiter=CSV_DELIMITER)
        return {row["id_do_trecho"]: _clean(row) for row in rows}


def _clean(row: dict) -> dict:
    indicator = (row.get("indicador") or "").strip().upper().split("_")[0]
    return {
        "indicador": NO_LABEL if indicator in ("", NO_LABEL.upper()) else indicator,
        "direcao": (row.get("direcao") or "").strip().lower() or NO_LABEL,
    }


def compare_label_sets(first: dict[str, dict], second: dict[str, dict]) -> dict:
    shared = sorted(set(first) & set(second))
    indicator_pairs = [(first[key]["indicador"], second[key]["indicador"]) for key in shared]
    same_indicator = [
        key
        for key in shared
        if first[key]["indicador"] == second[key]["indicador"]
        and first[key]["indicador"] != NO_LABEL
    ]
    return {
        "passages_compared": len(shared),
        "indicator": agreement_summary(*_columns(indicator_pairs)),
        "direction_when_same_indicator": agreement_summary(
            [first[key]["direcao"] for key in same_indicator],
            [second[key]["direcao"] for key in same_indicator],
        ),
    }


def _columns(pairs: list[tuple[str, str]]) -> tuple[list[str], list[str]]:
    return [pair[0] for pair in pairs], [pair[1] for pair in pairs]


def model_labels(results: dict[str, list[dict]]) -> dict[str, dict]:
    """Primary model item per passage: the strongest accepted one, or no label."""
    labels = {}
    for unit_id, items in results.items():
        if not items:
            labels[unit_id] = {"indicador": NO_LABEL, "direcao": NO_LABEL}
            continue
        best = max(items, key=lambda item: item["strength"])
        direction = "nao_se_aplica" if best["direction"] is None else f"{best['direction']:+d}"
        labels[unit_id] = {"indicador": best["indicator"], "direcao": direction.replace("+0", "0")}
    return labels
