"""Dated official reporting corroborates only the observed presidency, without backward fill."""

from copy import deepcopy

from crawlers.presidency.parsing import extract_chronology_text
from service.ingestion.contracts import IngestionError

LULA_CURRENT_SOURCE = (
    "https://www12.senado.leg.br/noticias/materias/2026/10/04/"
    "flavio-bolsonaro-e-lula-disputam-o-segundo-turno-das-eleicoes-para-presidente"
)
CURRENT_PERSON_LOCATOR = "Luiz Inácio Lula da Silva (PT), que busca a reeleição"
CURRENT_OFFICE_LOCATOR = "Lula exerce seu terceiro mandato como presidente"


def enrich_current_presidential_observation(acquisition, exercises):
    artifact = acquisition.acquire(LULA_CURRENT_SOURCE)
    text = " ".join(extract_chronology_text(artifact.path.read_bytes()).split())
    if CURRENT_PERSON_LOCATOR not in text or CURRENT_OFFICE_LOCATOR not in text:
        raise IngestionError("CONTEMPORARY_PRESIDENTIAL_PARTY_SOURCE_CHANGED")
    evidence = {
        "url": LULA_CURRENT_SOURCE, "sha256": artifact.sha256, "fetched_at": artifact.fetched_at,
        "locator": CURRENT_PERSON_LOCATOR + "; " + CURRENT_OFFICE_LOCATOR,
        "observed_on": "2026-10-04", "source_type": "contemporaneous_official_reporting",
    }
    enriched = deepcopy(exercises)
    for record in enriched:
        matches = (record["person_id"] == "arquivo-nacional-president:204"
                   and record["starts_on"] == "2023-01-01")
        if matches:
            record.setdefault("political_party_observations", []).append({
                "kind": "contemporaneous_presidential_party_observation",
                "political_party_abbreviation": "PT", "observed_on": "2026-10-04",
                "evidence": evidence,
            })
            record.setdefault("political_party_evidence", []).append(evidence)
    return enriched, evidence
