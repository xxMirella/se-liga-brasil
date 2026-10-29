"""Explicit editorial use of 2022 party estimates for the documented 2026 Senate."""

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

from service.political_dashboard.political_orientation_catalog import classify_political_orientation


@lru_cache(maxsize=1)
def senate_orientation_evidence():
    return json.loads(Path(__file__).with_suffix(".json").read_text())


def senate_editorial_orientation(political_party, year, institution_code):
    if year != 2026 or institution_code != "senado":
        return None
    requested_label = str(political_party or "").strip().casefold()
    for row in senate_orientation_evidence()["records"]:
        if row["political_party"].casefold() == requested_label:
            return deepcopy(row)
    return None


def classify_legislative_orientation(group, year, institution_code=None):
    observation = classify_political_orientation(group.get("abbreviation"), year)
    if observation["category"] == "unaffiliated":
        return observation
    if group.get("political_party_code") in {"unknown", "unreported", "unreconciled"}:
        return {"category": "undetermined", "status": "unverified_affiliation"}
    editorial = senate_editorial_orientation(group.get("abbreviation"), year, institution_code)
    return editorial or observation


def senate_orientation_summary(composition, year, counts):
    if year != 2026 or composition.get("institution_code") != "senado":
        return None
    if composition.get("total") != 81 or composition.get("territory_code") not in {None, "BR"}:
        return None
    if sum(counts.values()) != 81:
        return None
    total_seats = 81
    right = counts.get("right", 0) + counts.get("far_right", 0)
    majority = right > total_seats // 2
    disputed_parties = senate_orientation_evidence()["disputed_parties"]
    disputed = sum(group.get("count", 0) for group in composition.get("political_parties", [])
                   if group.get("abbreviation") in disputed_parties
                   and classify_legislative_orientation(group, year, "senado")["category"]
                   in {"right", "far_right"})
    from service.political_dashboard.senate_orientation_comparison import (
        compare_senate_classifications,
    )

    comparisons = compare_senate_classifications(
        composition, senate_orientation_evidence().get("comparison_methods", []),
    )
    return {"right_count": right, "total_seats": total_seats,
            "left_count": counts.get("left", 0), "center_count": counts.get("center", 0),
            "unaffiliated_count": counts.get("unaffiliated", 0),
            "unclassified_count": counts.get("undetermined", 0) + counts.get("controversial", 0),
            "majority_threshold": 41, "has_absolute_majority": majority,
            "reference_year": 2022, "classification_year": 2026,
            "evidence_kind": "editorial_application_of_dated_expert_estimate",
            "disputed_count": disputed, "right_excluding_disputed": max(0, right - disputed),
            "comparison_methods": comparisons,
            "snapshot_on": (composition.get("snapshot_on") or composition.get("reference_on")
                            or composition.get("observed_on"))}


def senate_summary_text(summary):
    from service.political_dashboard.senate_orientation_comparison import comparative_summary_text

    right, seats = summary["right_count"], summary["total_seats"]
    conclusion = ("Maioria de direita" if summary["has_absolute_majority"]
                  else "Sem maioria absoluta de direita comprovada")
    comparison = comparative_summary_text(summary.get("comparison_methods", []))
    return (f"{conclusion} pela referência acadêmica de 2022 aplicada à composição de 2026: "
            f"{right}/{seats} cadeiras; maioria absoluta exige 41. Síntese editorial, "
            "não medição acadêmica de 2026. PSD e MDB têm autodeclarações divergentes: "
            f"sem suas bancadas, direita {summary['right_excluding_disputed']}/{seats}. "
            "Pesquisa adicional sustenta o PSD como direita ou centro-direita; "
            "o MDB tem classificações acadêmicas divergentes. "
            f"{comparison} "
            f"Esquerda: {summary['left_count']}; centro: {summary['center_count']}; "
            f"sem filiação: {summary['unaffiliated_count']}; "
            f"sem classificação: {summary['unclassified_count']}. "
            "Não mede base do governo, presença em sessão ou orientação individual.")


def render_senate_orientation_summary(composition):
    summary = composition.get("orientation_summary")
    if not summary:
        return ""
    count = summary["right_count"]
    return (
        '<p class="panorama-leading-group"><strong>'
        f"Direita: {count}/{summary['total_seats']} cadeiras "
        "(referência de 2022 aplicada a 2026).</strong> "
        '<a href="/fontes-dos-dados#senado-2026">Fontes e critérios de classificação</a></p>'
    )


def senate_orientation_cell(summary):
    from service.political_dashboard.orientation_timeline import category_cell

    cell = category_cell(["right"] if summary["has_absolute_majority"] else ["undetermined"],
                         "partial")
    cell["label"] = ("Direita · maioria pela referência de 2022 (síntese 2026)"
                     if summary["has_absolute_majority"]
                     else "Sem maioria absoluta de direita comprovada · síntese 2026")
    cell["detail"] = senate_summary_text(summary)
    cell["orientation_summary"] = summary
    cell["source_evidence"] = [{
        "source_url": "https://doi.org/10.7910/DVN/MFIXKW",
        "source_title": "Survey de especialistas: referência 2022, aplicação editorial 2026",
        "source_publication_year": 2025,
    }, *senate_orientation_evidence()["documentary_sources"]]
    return cell
