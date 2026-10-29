"""Dated 1992-1994 Senate snapshots classified with an explicit, separate academic reference.

The 2018/2022 catalog never reaches these years. Party positions come from the 1993 wave of
Zucco and Power (2024); seats come from reconstructed snapshots whose gaps stay visible.
"""

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

SNAPSHOT_YEARS = (1992, 1993, 1994)
LEFT_RIGHT = ("left", "center", "right")
GAP_CATEGORY = "undetermined"
LOW_CONFIDENCE_SOURCES = frozenset(
    {
        "printed_anais_heading_same_year",
        "printed_diario_party_leadership_listing",
    }
)


@lru_cache(maxsize=1)
def senate_1992_1994_evidence():
    return json.loads(Path(__file__).with_suffix(".json").read_text())


def category_from_score(score, threshold):
    if score < -threshold:
        return "left"
    return "center" if score <= threshold else "right"


def party_category(party_key, evidence, threshold=None):
    """Return the dated category of a party label; unknown labels never become centre."""
    if party_key is None:
        return "party_not_identified"
    if party_key in evidence["unaffiliated_labels"]:
        return "unaffiliated"
    estimate = evidence["parties"].get(party_key)
    if estimate is None:
        return "party_without_estimate"
    return category_from_score(
        estimate["score"], threshold or evidence["classification_source"]["threshold"]
    )


def seat_category(seat, evidence, threshold=None):
    return party_category(seat["party"]["party_key"], evidence, threshold)


def empty_counts():
    return {
        "left": 0,
        "center": 0,
        "right": 0,
        "unaffiliated": 0,
        "party_without_estimate": 0,
        "party_not_identified": 0,
    }


def scenario_category(seat, evidence, scenario):
    """Apply one sensitivity scenario to one seat; unaffiliated seats are never moved."""
    category = seat_category(seat, evidence)
    if seat["party"]["source_kind"] in scenario.get("exclude_source_kinds", ()):
        category = "party_not_identified"
    if category == "party_not_identified":
        return scenario.get("gaps_to", category)
    if category == "unaffiliated":
        return category
    moved = scenario.get("moves", {}).get(seat["party"]["party_key"], category)
    return "party_without_estimate" if moved == "undetermined" else moved


def count_seats(seats, evidence, scenario=None):
    counts = empty_counts()
    for seat in seats:
        category = (
            scenario_category(seat, evidence, scenario)
            if scenario
            else seat_category(seat, evidence)
        )
        counts[category] += 1
    return counts


def scenario_result(seats, evidence, scenario):
    counts = count_seats(seats, evidence, scenario)
    threshold = evidence["majority_threshold"]
    return {
        "id": scenario["id"],
        "description": scenario["description"],
        "counts": counts,
        "right_has_majority": counts["right"] >= threshold,
        "left_has_majority": counts["left"] >= threshold,
    }


def snapshot_for(snapshot_on):
    return next(
        (
            row
            for row in senate_1992_1994_evidence()["snapshots"]
            if row["snapshot_on"] == snapshot_on
        ),
        None,
    )


def seat_quality(seats):
    roles = [seat["occupant_role"] for seat in seats]
    return {
        "seats": len(seats),
        "titular": roles.count("titular"),
        "substitute_in_exercise": roles.count("suplente_em_exercicio"),
        "titular_return_not_proven": roles.count("titular_retorno_provavel_nao_comprovado"),
        "ambiguous_occupant": roles.count("ocupante_ambiguo_titular_ou_suplente"),
        "vacant_documented": 0,
        "nominal_vote_within_120_days": sum(seat["nominal_vote_within_120_days"] for seat in seats),
    }


def snapshot_summary(snapshot_on):
    """Counts, majority bounds and sensitivity for one reconstructed 31 December snapshot."""
    evidence = senate_1992_1994_evidence()
    snapshot = snapshot_for(snapshot_on)
    if snapshot is None:
        return None
    seats = snapshot["seats"]
    counts = count_seats(seats, evidence)
    threshold = evidence["majority_threshold"]
    unresolved = counts["party_without_estimate"] + counts["party_not_identified"]
    scenarios = [
        scenario_result(seats, evidence, item) for item in evidence["sensitivity_scenarios"]
    ]
    return {
        "snapshot_on": snapshot_on,
        "total_seats": evidence["total_seats"],
        "counts": counts,
        "counted_seats": sum(counts.values()),
        "majority_threshold": threshold,
        "right_has_majority": counts["right"] >= threshold,
        "left_has_majority": counts["left"] >= threshold,
        "right_possible_if_gaps_were_right": counts["right"] + unresolved >= threshold,
        "left_possible_if_gaps_were_left": counts["left"] + unresolved >= threshold,
        "unresolved_party_seats": unresolved,
        "seat_quality": seat_quality(seats),
        "sensitivity": scenarios,
        "any_scenario_with_majority": sorted(
            item["id"]
            for item in scenarios
            if item["right_has_majority"] or item["left_has_majority"]
        ),
        "evidence_kind": "editorial_application_of_dated_expert_estimate",
        "reference_wave": 1993,
    }


def year_snapshot_summary(year, institution_code="senado"):
    if institution_code != "senado" or year not in SNAPSHOT_YEARS:
        return None
    return snapshot_summary(f"{year}-12-31")


def conclusion_label(summary):
    if summary["right_has_majority"]:
        return "Maioria de direita"
    if summary["left_has_majority"]:
        return "Maioria de esquerda"
    return "Sem maioria absoluta de direita nem de esquerda comprovada"


def gap_sentence(summary):
    if summary["right_has_majority"]:
        return ""
    if summary["right_possible_if_gaps_were_right"]:
        return (
            "A direita só alcançaria 41 se todas as cadeiras sem partido identificado "
            "ou sem estimativa fossem de direita."
        )
    return "Mesmo somando todas essas lacunas, a direita não alcançaria 41."


def summary_text(summary):
    counts = summary["counts"]
    year, month, day = summary["snapshot_on"].split("-")
    return (
        f"{conclusion_label(summary)} em {year} pela onda de 1993 de Zucco e Power, "
        f"aplicada à fotografia de {day}/{month}: "
        f"direita {counts['right']}/{summary['total_seats']}; centro {counts['center']}; "
        f"esquerda {counts['left']}; sem filiação {counts['unaffiliated']}; "
        f"partido sem estimativa {counts['party_without_estimate']}; "
        f"partido não identificado {counts['party_not_identified']}. "
        f"Maioria absoluta exige 41. {gap_sentence(summary)} "
        "Síntese editorial reconstruída, não relatório oficial das 81 cadeiras."
    )


def senate_1992_1994_cell(year):
    summary = year_snapshot_summary(year)
    if summary is None:
        return None
    from service.political_dashboard.orientation_timeline import category_cell

    majority = summary["right_has_majority"] or summary["left_has_majority"]
    category = "right" if summary["right_has_majority"] else "left"
    cell = category_cell([category] if majority else [GAP_CATEGORY], "partial")
    cell["label"] = (
        f"{conclusion_label(summary)} · síntese editorial"
        if majority
        else "Sem maioria de direita nem de esquerda comprovada · síntese editorial"
    )
    cell["detail"] = summary_text(summary)
    cell["orientation_summary"] = summary
    cell["source_evidence"] = deepcopy(senate_1992_1994_evidence()["documentary_sources"])
    return cell
