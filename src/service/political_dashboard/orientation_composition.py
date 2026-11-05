"""Count documented members by classifications valid in the selected year only."""

from collections import Counter

from service.political_dashboard.political_orientation_catalog import classify_political_orientation
from service.public_profile_web.security import text


def orientation_composition(composition, year):
    from service.political_dashboard.camara_orientation import chamber_policy_applies
    from service.political_dashboard.chamber_party_identity import HISTORICAL_IDENTITY_POLICY
    from service.political_dashboard.orientation_timeline import ORIENTATION_LABELS

    chamber_policy = chamber_policy_applies(composition, year)
    counts = Counter()
    for group in composition.get("political_parties", []):
        category = group_orientation_category(
            group, year, composition.get("institution_code"), chamber_policy=chamber_policy,
            identity_alignment=composition.get("orientation_policy_version")
            == HISTORICAL_IDENTITY_POLICY,
        )
        counts[category] += group["count"]
    unreported = (composition.get("total") or 0) - sum(counts.values())
    if unreported > 0:
        counts["undetermined"] += unreported
    from service.political_dashboard.senate_orientation_2026 import senate_orientation_summary

    return dict(
        composition,
        composition_view="political_orientation",
        classification_year=year,
        orientation_summary=senate_orientation_summary(composition, year, counts),
        political_parties=[
            {
                "abbreviation": ORIENTATION_LABELS[category],
                "count": count,
                "orientation_category": category,
            }
            for category, count in counts.items()
            if count
        ],
    )


def group_orientation_category(group, year, institution_code=None, *, chamber_policy=False,
                               identity_alignment=False):
    if year == 2026 and institution_code == "senado":
        from service.political_dashboard.senate_orientation_2026 import (
            classify_legislative_orientation,
        )

        return classify_legislative_orientation(group, year, institution_code)["category"]
    if chamber_policy:
        from service.political_dashboard.camara_orientation import chamber_orientation

        return chamber_orientation(group, year, identity_alignment=identity_alignment)["category"]
    category = classify_political_orientation(group.get("abbreviation"), year)["category"]
    if category != "unaffiliated" and group.get("political_party_code") in {
        "unreported",
        "unknown",
        "unreconciled",
    }:
        return "undetermined"
    return category


def render_orientation_composition_note(composition, year, reference_on):
    reference = composition.get("snapshot_on") or composition.get("reference_on") or reference_on
    editorial = year == 2026 and composition.get("institution_code") == "senado"
    from service.political_dashboard.camara_orientation import chamber_policy_applies

    if chamber_policy_applies(composition, year):
        reference_year = 2018 if year < 2022 else 2022
        return (
            '<p class="panorama-caption panorama-orientation-composition-note">'
            f"Câmara · fotografia em {text(reference)}. Survey de {reference_year}; "
            "aplicação editorial nos demais anos, com sensibilidade abaixo. "
            "Não mede orientação individual ou apoio ao governo.</p>"
        )
    available = year in {2018, 2022}
    limitation = (
        "Classificação dos partidos no ano pesquisado; não avalia ações individuais."
        if available
        else "Não há classificação documentada para este ano. "
        "Não usamos a classificação de outros anos."
    )
    if editorial:
        return (
            '<p class="panorama-caption panorama-orientation-composition-note">'
            f"Integrantes na composição documentada para {year}</p>"
        )
    return (
        '<p class="panorama-caption panorama-orientation-composition-note">'
        f"Integrantes na composição documentada para {year}"
        + (f" · referência: {text(reference)}" if reference else "")
        + ". Não é contagem de presença em sessão. "
        + limitation
        + " Sem filiação e sem classificação permanecem separados.</p>"
    )
