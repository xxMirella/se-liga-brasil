"""Apply each reviewed alternative method separately to the same Senate roster."""

from collections import Counter

UNVERIFIED_AFFILIATIONS = frozenset({"unknown", "unreported", "unreconciled"})
UNAFFILIATED_LABELS = frozenset({"s/partido", "sem partido", "sem filiação partidária"})


def comparative_category(group, method):
    label = str(group.get("abbreviation") or "").strip()
    if label.casefold() in UNAFFILIATED_LABELS:
        return "unaffiliated"
    if group.get("political_party_code") in UNVERIFIED_AFFILIATIONS:
        return "undetermined"
    return next((category for category in ("left", "center", "right")
                 if label in method[category]), "undetermined")


def compare_senate_classifications(composition, methods):
    results = []
    for method in methods:
        counts = Counter()
        for group in composition.get("political_parties", []):
            counts[comparative_category(group, method)] += group.get("count", 0)
        counts["undetermined"] += max(0, (composition.get("total") or 0) - sum(counts.values()))
        results.append({"methodology_id": method["methodology_id"], "label": method["label"],
                        "source_url": method["source_url"], "counts": dict(counts),
                        "source_publication_year": method["source_publication_year"],
                        "reference_period": method["reference_period"],
                        "has_absolute_majority": counts["right"] > 40,
                        "evidence_kind": "editorial_application_of_historical_classification"})
    return results


def comparative_summary_text(comparisons):
    return " ".join(
        f"{row['label']}: direita {row['counts'].get('right', 0)}/81 "
        "com MDB no centro."
        for row in comparisons
    )
