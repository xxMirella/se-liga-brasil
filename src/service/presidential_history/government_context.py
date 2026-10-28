"""Keep governing-party support context separate from presidential affiliation."""

from copy import deepcopy

from crawlers.presidency.reviewed_transcriptions import ARENA_REGISTRATION_SOURCE_URL
from service.presidential_history.party_collection import acquire_claim_source

CASTELO_BIOGRAPHY = (
    "https://presidentes.an.gov.br/index.php/centro-de-referencia-de-acervos-presidenciais/"
    "assuntos/biografias/196-humberto-de-alencar-castelo-branco"
)
SUPPORT_LOCATOR = "Aliança Renovadora Nacional (Arena), de apoio ao governo"


def enrich_documented_government_context(acquisition, exercises, transcriptions):
    from service.ingestion.contracts import IngestionError

    enriched = deepcopy(exercises)
    targets = [row for row in enriched if row["person_id"] == "arquivo-nacional-president:196"
               and row["starts_on"] == "1964-04-15"]
    if not targets:
        return enriched
    registration, _ = acquire_claim_source(
        acquisition, ARENA_REGISTRATION_SOURCE_URL, transcriptions,
    )
    supporting, source_text = acquire_claim_source(acquisition, CASTELO_BIOGRAPHY, transcriptions)
    if SUPPORT_LOCATOR not in source_text:
        raise IngestionError("PRESIDENTIAL_GOVERNMENT_CONTEXT_SOURCE_CHANGED")
    observation = {
        "date": "1966-03-24", "year": 1966, "date_precision": "day",
        "title": "Registro da organização governista", "organization": "ARENA",
        "relationship": "government_support_organization_not_personal_affiliation",
        "summary": (
            "O TSE registrou a ARENA como organização com atribuições partidárias em "
            "24/03/1966. O Arquivo Nacional a descreve como apoio ao governo Castelo Branco. "
            "Sua transformação em partido foi deferida em 07/03/1967. "
            "Esses documentos não comprovam a filiação pessoal do presidente."
        ),
        "source_url": ARENA_REGISTRATION_SOURCE_URL,
        "evidence": [registration, dict(supporting, locator=SUPPORT_LOCATOR)],
    }
    for exercise in targets:
        exercise["government_context_observations"] = [deepcopy(observation)]
    return enriched
