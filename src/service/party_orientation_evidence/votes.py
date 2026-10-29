"""Thematic roll calls to vote evidence: one record per party and roll call, never from PCA axes."""

from collections import defaultdict
from collections.abc import Callable
from datetime import date

from service.party_orientation_evidence.records import (
    PROOF_PRIMARY,
    PROOF_REPORTED,
    dimension_of,
    evidence_record,
)
from service.party_orientation_model.contracts import LAYER_VOTES, Rubric, normalize_party_key
from service.party_vote_analysis.legislatures import government_on
from service.party_vote_analysis.thematic_scores import MINIMUM_VOTERS

INDICATIVE_BELOW_VOTINGS = 3
NON_PARTY_LABELS = frozenset({"s.part.", "sem partido", "s/partido"})
COALITION_FIRST_YEAR, COALITION_LAST_YEAR = 2003, 2014
ATTRIBUTION = "member_votes_by_affiliation_at_vote_date"
# A request for urgency or preference is a procedural vote, not a position on the policy.
PROCEDURAL_MARKERS = ("requerimento", "rqs", "preferência")
COMPOSITE_ITEMS = {
    "biosseguranca_2005": "proposição composta (transgênicos e células-tronco): o voto pode não "
    "refletir a posição sobre pesquisa com células-tronco."
}
SourceLookup = Callable[[str, int], str]  # (chamber, year) -> URL of the official year file
Tallies = dict[str, dict[str, dict[str, int]]]  # voting_id -> party -> {"sim", "nao"}


def is_procedural(roll_call: dict) -> bool:
    description = roll_call["description"].casefold()
    return any(marker in description for marker in PROCEDURAL_MARKERS)


def procedural_voting_ids(blocks: list[dict]) -> list[str]:
    return sorted(
        f"{block['chamber']}:{roll_call['voting_id']}"
        for block in blocks
        for roll_call in block["thematic_roll_calls"]
        if is_procedural(roll_call)
    )


def pole_stance(yes: int, no: int, yes_sign: int) -> float:
    """2 * share toward the indicator's positive pole - 1 (rubric aggregation rule)."""
    share_yes = yes / (yes + no)
    return 2 * (share_yes if yes_sign > 0 else 1 - share_yes) - 1


def decided_parties(counts_by_party: dict[str, dict[str, int]]) -> dict[str, tuple[int, int]]:
    """Parties with enough yes/no votes; non-party labels never become a party."""
    return {
        party: (counts.get("sim", 0), counts.get("nao", 0))
        for party, counts in counts_by_party.items()
        if party.casefold() not in NON_PARTY_LABELS
        and counts.get("sim", 0) + counts.get("nao", 0) >= MINIMUM_VOTERS
    }


def merit_roll_calls(block: dict) -> list[dict]:
    return [roll_call for roll_call in block["thematic_roll_calls"] if not is_procedural(roll_call)]


def count_votings_per_dimension(
    block: dict, tallies: Tallies, rubric: Rubric
) -> dict[tuple[str, str], int]:
    counted: dict[tuple[str, str], int] = defaultdict(int)
    for roll_call in merit_roll_calls(block):
        dimension = dimension_of(rubric, roll_call["indicator_id"])
        for party in decided_parties(tallies.get(roll_call["voting_id"], {})):
            counted[(normalize_party_key(party), dimension)] += 1
    return counted


def government_agreement(block: dict) -> dict[str, dict]:
    return {normalize_party_key(row["party"]): row for row in block["government_alignment"]}


def describe(block: dict, roll_call: dict, party: str, agreement: dict, indicative: bool) -> str:
    voted_on = date.fromisoformat(roll_call["voted_on"])
    pole = "positivo" if roll_call["yes_sign"] > 0 else "negativo"
    parts = [
        f"{block['chamber']} {roll_call['voted_on']}: {roll_call['theme']}. "
        f"Voto 'sim' leva ao polo {pole} de {roll_call['indicator_id']}. {roll_call['rationale']}",
        f"Governo do dia: {government_on(voted_on) or 'n/d'} (descritor N1, fora da escala).",
    ]
    row = agreement.get(normalize_party_key(party))
    if row:
        parts.append(
            f"Concordância do partido com o governo na legislatura: {row['agreement']:.0%} "
            f"em {row['n_roll_calls']} votações."
        )
    if COALITION_FIRST_YEAR <= voted_on.year <= COALITION_LAST_YEAR:
        parts.append("2003-2014: coalizões heterogêneas; voto lido isoladamente, sem eixo de PCA.")
    if roll_call["item_id"] in COMPOSITE_ITEMS:
        parts.append(f"Atenção: {COMPOSITE_ITEMS[roll_call['item_id']]}")
    if indicative:
        parts.append(
            f"Indicativo: menos de {INDICATIVE_BELOW_VOTINGS} votações temáticas nesta dimensão "
            "na legislatura; peso reduzido (nível 'reported')."
        )
    return " ".join(parts)


def thematic_vote_records(
    block: dict, tallies: Tallies, source_url: SourceLookup, rubric: Rubric
) -> list[dict]:
    per_dimension = count_votings_per_dimension(block, tallies, rubric)
    agreement = government_agreement(block)
    records = []
    for roll_call in merit_roll_calls(block):
        dimension = dimension_of(rubric, roll_call["indicator_id"])
        year = int(roll_call["voted_on"][:4])
        for party, (yes, no) in decided_parties(tallies.get(roll_call["voting_id"], {})).items():
            indicative = per_dimension[(normalize_party_key(party), dimension)] < (
                INDICATIVE_BELOW_VOTINGS
            )
            records.append(
                evidence_record(
                    evidence_id=f"votes:{block['chamber']}:{roll_call['voting_id']}:"
                    f"{normalize_party_key(party)}",
                    political_party=party,
                    layer=LAYER_VOTES,
                    dimension=dimension,
                    indicator_id=roll_call["indicator_id"],
                    stance=pole_stance(yes, no, roll_call["yes_sign"]),
                    source_id=f"{block['chamber']}-roll-call-{roll_call['voting_id']}",
                    source_url=source_url(block["chamber"], year),
                    source_date=date.fromisoformat(roll_call["voted_on"]),
                    year_start=year,
                    year_end=year,
                    proof_level=PROOF_REPORTED if indicative else PROOF_PRIMARY,
                    attribution_basis=ATTRIBUTION,
                    description=describe(block, roll_call, party, agreement, indicative),
                )
            )
    return records


def vote_conversion_notes(procedural_ids: list[str]) -> list[str]:
    return [
        f"Votações processuais (requerimento de urgência ou preferência) não são posição sobre a "
        f"política e ficam fora: {', '.join(procedural_ids) or 'nenhuma'}.",
        "Convertidos apenas os votos nominais temáticos com direção do voto 'sim' codificada e "
        "fonte no catálogo curado (service/party_vote_analysis/thematic_catalog.py).",
        "Eixos de PCA (D1/D2) NÃO são convertidos: D1 mistura ideologia e governo x oposição "
        "(correlação +0,99 na 56a e -0,81 na 57a legislatura) e em 2003-2014 coalizões juntam "
        "partidos de lados opostos; só seria usado com outra evidência independente.",
        "Coesão (Rice), concordância com o governo e seguimento da orientação de líderes não são "
        "posição ideológica: aparecem apenas na descrição das evidências (descritor N1).",
        "Menos de 3 votações temáticas do partido na dimensão e legislatura = indicativo: "
        "recebe o nível de prova 'reported' (multiplicador 0,4).",
        "Mínimo de 3 votantes sim/não por partido e votação; rótulo 'S.PART.' é descartado.",
        "Temas sem indicador na rubrica ficam fora (ver excluded_themes no arquivo de posições).",
    ]
