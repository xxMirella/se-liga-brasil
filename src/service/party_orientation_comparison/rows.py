"""Join survey estimates and model classifications per political party and period."""

from dataclasses import dataclass

GROUP_LABELS = {
    "left": "Esquerda",
    "center": "Centro",
    "right": "Direita",
    "undetermined": "Sem classificação",
    "controversial": "Classificação controversa",
    "mixed": "Perfil misto",
}
OUTCOME_LABELS = {
    "agree": "Concorda",
    "disagree": "Discorda",
    "mixed": "Concorda em parte",
    "not_comparable": "Não comparável",
}
OUTCOME_ORDER = tuple(OUTCOME_LABELS)
SIDES = ("left", "center", "right")
SURVEY_SCALE_MIDPOINT = 5.0  # catalog scale 0-10; model scale -1..+1 maps as 5 + 5 * score


@dataclass(frozen=True)
class ComparisonRow:
    political_party: str
    period_id: str
    year_start: int
    year_end: int
    survey: list
    model: dict | None
    outcome: str
    reason: str


def model_score_on_survey_scale(overall_score):
    return None if overall_score is None else SURVEY_SCALE_MIDPOINT * (1 + overall_score)


def model_group(model):
    if model is None or model.get("no_evidence"):
        return "undetermined"
    return model["group"]


def compare_groups(survey, model):
    """Return (outcome, reason_code); never fills a missing side with a guess."""
    if not survey:
        return "not_comparable", "survey_not_covering_period"
    group = model_group(model)
    if group not in SIDES:
        return "not_comparable", f"model_{group}"
    matches = sum(1 for entry in survey if entry["group"] == group)
    if matches == len(survey):
        return "agree", "same_side"
    return ("disagree" if matches == 0 else "mixed"), "different_side"


def reason_text(reason_code, survey, model):
    groups = " e ".join(sorted({GROUP_LABELS[entry["group"]].lower() for entry in survey}))
    texts = {
        "survey_not_covering_period": (
            "A pesquisa de especialistas só estima os anos de 2018 e 2022; "
            "não há estimativa para este período."
        ),
        "model_undetermined": "O modelo não tem evidência suficiente para classificar o período.",
        "model_mixed": "O modelo encontrou perfil misto, sem lado único para comparar.",
        "model_controversial": "O modelo registrou classificação controversa, sem lado único.",
        "same_side": f"Pesquisa e modelo ficam do mesmo lado ({groups}).",
        "different_side": (
            f"A pesquisa aponta {groups}; o modelo aponta "
            f"{GROUP_LABELS.get(model_group(model), '').lower()}."
        ),
    }
    return texts[reason_code]


def build_row(political_party, row, periods_by_id):
    period = periods_by_id[row["period_id"]]
    outcome, reason_code = compare_groups(row["survey"], row["model"])
    return ComparisonRow(
        political_party,
        row["period_id"],
        period["year_start"],
        period["year_end"],
        row["survey"],
        row["model"],
        outcome,
        reason_text(reason_code, row["survey"], row["model"]),
    )


def party_entry(snapshot, political_party):
    wanted = political_party.casefold()
    for entry in snapshot["political_parties"]:
        if entry["political_party"].casefold() == wanted:
            return entry
    return None


def build_rows(snapshot, political_party):
    entry = party_entry(snapshot, political_party)
    if entry is None:
        raise ValueError("UNKNOWN_POLITICAL_PARTY")
    periods_by_id = {period["period_id"]: period for period in snapshot["periods"]}
    rows = [build_row(entry["political_party"], row, periods_by_id) for row in entry["rows"]]
    return sorted(rows, key=lambda item: item.year_start)


def outcome_counts(rows):
    counts = dict.fromkeys(OUTCOME_ORDER, 0)
    for row in rows:
        counts[row.outcome] += 1
    return counts
