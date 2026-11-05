"""Didactic "who is represented?" example (a chocolate vote), as pure functions.

Ported from the `choco()` logic of the Panorama v3 design: 100 people, three groups, three seat
scenarios and two proposals. Nothing here is real data; it only explains the majority rule.
"""

from dataclasses import dataclass

TOTAL_PEOPLE = 100
VOTES_TO_PASS = TOTAL_PEOPLE // 2 + 1  # 51: more than half


@dataclass(frozen=True)
class PopulationGroup:
    key: str
    label: str
    population_percent: int
    color_key: str  # suffix source of the `ds-bloc--*` color class


POPULATION_GROUPS = (
    PopulationGroup("likes", "Gostam de chocolate", 60, "chocolate_likes"),
    PopulationGroup("allergic", "Têm alergia", 15, "chocolate_allergic"),
    PopulationGroup("dislikes", "Não gostam", 25, "chocolate_dislikes"),
)
SCENARIO_LABELS = {
    "prop": "Espelha a população",
    "conc": "Uma maioria concentrada",
    "equi": "Mais equilibrada",
}
SEATS_BY_SCENARIO = {"prop": (60, 15, 25), "conc": (85, 0, 15), "equi": (45, 20, 35)}
PROPOSAL_LABELS = {"A": "Chocolate em toda merenda", "B": "Opção sem chocolate na merenda"}
GROUPS_IN_FAVOR = {"A": ("likes",), "B": ("allergic", "dislikes")}
UNREPRESENTED_PHRASES = {"allergic": "têm alergia"}


@dataclass(frozen=True)
class ChocolateExplanation:
    seats_by_group: tuple[int, ...]  # aligned with POPULATION_GROUPS
    seat_group_keys: tuple[str, ...]  # one entry per seat, in group order
    votes_in_favor: int
    approved: bool
    seats_text: str
    vote_title: str
    vote_text: str
    unrepresented_text: str  # empty when every group holds at least one seat


def votes_in_favor(seats_by_group, proposal):
    in_favor = GROUPS_IN_FAVOR[proposal]
    pairs = zip(POPULATION_GROUPS, seats_by_group, strict=True)
    return sum(seats for group, seats in pairs if group.key in in_favor)


def vote_extra_sentence(proposal, approved, seats_by_group, in_favor):
    """Sentence that explains what the result means for the groups that lost or won."""
    missing = VOTES_TO_PASS - in_favor
    if not approved and proposal == "B":
        return (
            f" Para aprovar, quem tem alergia e quem não gosta precisam convencer {missing} "
            "pessoas que gostam de chocolate, e isso só acontece se a realidade delas for ouvida."
        )
    if not approved:
        return (
            f" Quem gosta de chocolate precisaria do apoio de {missing} "
            "representantes dos outros grupos."
        )
    if proposal == "A" and seats_by_group[1] > 0:
        return (
            " Os alérgicos votaram contra e perderam, mas com cadeiras podem propor ajustes e "
            "cobrar alternativas."
        )
    if proposal == "B":
        return " Grupos menores, somados, formaram maioria."
    return ""


def seats_summary(seats_by_group):
    """The group whose share of seats differs most from its share of the population."""
    gaps = [
        (seats - group.population_percent, group, seats)
        for group, seats in zip(POPULATION_GROUPS, seats_by_group, strict=True)
    ]
    gap, group, seats = max(gaps, key=lambda item: abs(item[0]))
    if gap == 0:
        return "Cada grupo tem cadeiras na mesma proporção que tem na população."
    return f"{group.label}: {group.population_percent}% da população, {seats}% das cadeiras."


def unrepresented_summary(seats_by_group):
    sentences = [
        f"As {group.population_percent} pessoas que "
        f"{UNREPRESENTED_PHRASES.get(group.key, group.label.lower())} não têm nenhuma cadeira. "
        "Ninguém leva a realidade delas para a votação."
        for group, seats in zip(POPULATION_GROUPS, seats_by_group, strict=True)
        if group.population_percent > 0 and seats == 0
    ]
    return " ".join(sentences)


def build_chocolate_explanation(scenario, proposal):
    seats_by_group = SEATS_BY_SCENARIO[scenario]
    in_favor = votes_in_favor(seats_by_group, proposal)
    approved = in_favor >= VOTES_TO_PASS
    extra = vote_extra_sentence(proposal, approved, seats_by_group, in_favor)
    verdict = "aprovada." if approved else "rejeitada."
    return ChocolateExplanation(
        seats_by_group=seats_by_group,
        seat_group_keys=tuple(
            group.color_key
            for group, seats in zip(POPULATION_GROUPS, seats_by_group, strict=True)
            for _ in range(seats)
        ),
        votes_in_favor=in_favor,
        approved=approved,
        seats_text=seats_summary(seats_by_group),
        vote_title=f"{in_favor} a favor, {TOTAL_PEOPLE - in_favor} contra: {verdict}",
        vote_text=f"Precisa de {VOTES_TO_PASS}, mais da metade.{extra}",
        unrepresented_text=unrepresented_summary(seats_by_group),
    )
