"""Maps the project's dated party classification to panorama blocs. No classification is made here.

Rule: the category comes from `group_orientation_category` (catalog, Chamber policy and Senate
editorial evidence of the sampled year). Its keys equal the bloc keys. A category the panorama
does not know becomes `undetermined`; party labels that mean "no party" become `unaffiliated`
before the catalog is asked; seats a house reports without a party are `undetermined`.
"""

from collections import Counter

from service.majority_panorama.blocs import BLOC_KEYS

UNAFFILIATED_LABELS = frozenset(
    {"s.part.", "s/partido", "sem partido", "sem filiação partidária"}
)
UNREPORTED_PARTY_LABEL = "Sem partido informado"


def is_unaffiliated_label(label):
    return str(label or "").strip().casefold() in UNAFFILIATED_LABELS


def bloc_key_for_political_party(group, year, composition):
    """Bloc of one party group of `composition`, classified for the sampled `year`."""
    if is_unaffiliated_label(group.get("abbreviation")):
        return "unaffiliated"
    from service.political_dashboard.camara_orientation import chamber_policy_applies
    from service.political_dashboard.chamber_party_identity import HISTORICAL_IDENTITY_POLICY
    from service.political_dashboard.orientation_composition import group_orientation_category

    category = group_orientation_category(
        group, year, composition.get("institution_code"),
        chamber_policy=chamber_policy_applies(composition, year),
        identity_alignment=composition.get("orientation_policy_version")
        == HISTORICAL_IDENTITY_POLICY,
    )
    return category if category in BLOC_KEYS else "undetermined"


def seats_by_political_party(composition):
    """Seats per party abbreviation; repeated abbreviations are summed."""
    seats = Counter()
    for group in composition.get("political_parties") or ():
        seats[group["abbreviation"]] += group["count"]
    return seats


def classify_political_parties(composition, year):
    """(seats per bloc, {bloc: [(political_party, seats)]} ordered by seats desc).

    Seats the house counts but attributes to no party fill `undetermined`, under the label
    `UNREPORTED_PARTY_LABEL`, so the bloc totals always add up to `composition["total"]`.
    """
    groups = {}
    for group in composition.get("political_parties") or ():
        groups.setdefault(group["abbreviation"], group)
    seats = seats_by_political_party(composition)
    parties_by_bloc = {}
    for abbreviation, count in seats.items():
        bloc_key = bloc_key_for_political_party(groups[abbreviation], year, composition)
        parties_by_bloc.setdefault(bloc_key, []).append((abbreviation, count))
    unreported = composition["total"] - sum(seats.values())
    if unreported > 0:
        parties_by_bloc.setdefault("undetermined", []).append(
            (UNREPORTED_PARTY_LABEL, unreported)
        )
    for entries in parties_by_bloc.values():
        entries.sort(key=lambda entry: (-entry[1], entry[0]))
    counts = {key: sum(count for _, count in entries) for key, entries in parties_by_bloc.items()}
    return counts, parties_by_bloc
