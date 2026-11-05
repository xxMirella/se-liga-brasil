"""Classification of composition groups that are real political parties."""

NON_PARTY_LABELS = frozenset({"s/partido", "sem partido", "não informado", "não identificado"})


def is_political_party(group):
    label = group["abbreviation"].strip().casefold()
    if group.get("political_party_code") in {"unreported", "unknown", "unreconciled"}:
        return False
    return label not in NON_PARTY_LABELS and not label.startswith(
        ("filiação ", "desconhecid", "sem partido", "sem filiação", "não identif", "não informad")
    )
