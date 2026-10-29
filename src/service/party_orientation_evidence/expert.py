"""Expert survey estimates as calibration references (weight 0 in the model, never scored)."""

from datetime import date

from service.party_orientation_evidence.records import PROOF_SECONDARY, evidence_record
from service.party_orientation_model.contracts import (
    DIMENSION_OVERALL,
    LAYER_EXPERT,
    normalize_party_key,
)

INDICATOR = "expert_position"
ATTRIBUTION = "survey_of_experts"
BOLOGNESI_METHODOLOGY = "bolognesi_expert_mean_0_10_v1"
ZUCCO_URL = "https://dataverse.harvard.edu/api/access/datafile/1412580"  # hardcode-ok: fonte
ZUCCO_PUBLICATION_DATE = date(2009, 1, 1)  # only the year of publication is recorded
ZUCCO_WAVES = (1990, 1993, 1997, 2001, 2005)
ZUCCO_MIDPOINT, ZUCCO_HALF_RANGE = 5.5, 4.5  # 1-10 scale, 1 = left
BOLOGNESI_MIDPOINT, BOLOGNESI_HALF_RANGE = 5.0, 5.0  # 0-10 scale, 0 = left


def scaled_stance(value: float, midpoint: float, half_range: float) -> float:
    return max(-1.0, min(1.0, (value - midpoint) / half_range))


def bolognesi_records(observations: list[dict]) -> list[dict]:
    """Rows of the published catalog; their original survey column and URL are preserved."""
    return [
        evidence_record(
            evidence_id=f"expert:bolognesi:{row['reference_year']}:"
            f"{normalize_party_key(row['political_party'])}",
            political_party=row["political_party"],
            layer=LAYER_EXPERT,
            dimension=DIMENSION_OVERALL,
            indicator_id=INDICATOR,
            stance=scaled_stance(row["score"], BOLOGNESI_MIDPOINT, BOLOGNESI_HALF_RANGE),
            source_id=f"bolognesi-experts-{row['reference_year']}-{row['source_column']}",
            source_url=row["source_url"],
            source_date=date(row["reference_year"], 12, 31),
            year_start=row["reference_year"],
            year_end=row["reference_year"],
            proof_level=PROOF_SECONDARY,
            attribution_basis=ATTRIBUTION,
            description=(
                f"Média de {row['respondents']} especialistas (0 = esquerda, 10 = direita): "
                f"{row['score']:.2f}. Data = fim do ano da pesquisa (data de campo não registrada)."
            ),
        )
        for row in observations
        if row.get("methodology_id") == BOLOGNESI_METHODOLOGY
    ]


def zucco_records(estimates: dict[str, dict[int, float]]) -> list[dict]:
    """party label -> wave year -> estimate (1-10); labels are the survey's own."""
    return [
        evidence_record(
            evidence_id=f"expert:power-zucco:{wave}:{normalize_party_key(label)}",
            political_party=label,
            layer=LAYER_EXPERT,
            dimension=DIMENSION_OVERALL,
            indicator_id=INDICATOR,
            stance=scaled_stance(value, ZUCCO_MIDPOINT, ZUCCO_HALF_RANGE),
            source_id=f"power-zucco-2009-party-estimates-{wave}",
            source_url=ZUCCO_URL,
            source_date=ZUCCO_PUBLICATION_DATE,
            year_start=wave,
            year_end=wave,
            proof_level=PROOF_SECONDARY,
            attribution_basis=ATTRIBUTION,
            description=(
                f"Estimativa de legisladores (Power e Zucco 2009; 1 = esquerda, 10 = direita) da "
                f"onda {wave}: {value:.2f}. Data = ano de publicação (dia não registrado)."
            ),
        )
        for label, by_wave in estimates.items()
        for wave, value in by_wave.items()
        if wave in ZUCCO_WAVES
    ]


def expert_conversion_notes() -> list[str]:
    return [
        "Referência de calibração: peso 0 no motor (decisão R8). Nunca entra no escore; o "
        "relatório mostra a distância entre o escore comportamental e a estimativa.",
        "Bolognesi: linhas do catálogo atual (2018 e 2022), com a sigla da pesquisa; "
        "Power e Zucco: party.estimates de 1990 a 2005 do Dataverse, com a sigla do arquivo. "
        "Sem herança de sigla.",
    ]
