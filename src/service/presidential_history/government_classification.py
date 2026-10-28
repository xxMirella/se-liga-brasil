"""Research classifications of government parties are not personal affiliation certificates."""

from copy import deepcopy

from crawlers.presidency.parsing import extract_chronology_text
from service.ingestion.contracts import IngestionError
from service.presidential_history.biographies import exercise_year_bounds

RESEARCH_URL = "https://educapes.capes.gov.br/handle/capes/766428"
RESEARCH_TITLE = (
    "Partidos políticos e política externa: a América do Sul nos governos Fernando Henrique "
    "Cardoso/PSDB (1995/2002) e Lula da Silva/PT (2003/2010)"
)
CLASSIFIED_GOVERNMENTS = (
    ("arquivo-nacional-president:197", 1995, 2002, "PSDB",
     "Partido da Social Democracia Brasileira"),
    ("arquivo-nacional-president:204", 2003, 2010, "PT", "Partido dos Trabalhadores"),
)


def classify_documented_government(record, classification, evidence):
    identifier, year_start, year_end, abbreviation, name = classification
    first_year, last_year = exercise_year_bounds(record)
    if record["person_id"] != identifier or last_year < year_start or first_year > year_end:
        return
    record.update(
        political_party_code="historical-government:BR:" + abbreviation,
        political_party=name, political_party_abbreviation=abbreviation,
        political_party_status="verified_government_classification",
        political_party_context="original_research_government_classification",
        political_party_year_start=year_start, political_party_year_end=year_end,
        political_party_evidence=[evidence],
        political_party_limitation="classification_of_government_not_affiliation_certificate",
    )


def enrich_documented_government_classifications(acquisition, exercises):
    artifact = acquisition.acquire(RESEARCH_URL)
    text = " ".join(extract_chronology_text(artifact.path.read_bytes()).split())
    if RESEARCH_TITLE not in text or "Universidade Federal Fluminense" not in text:
        raise IngestionError("PRESIDENTIAL_RESEARCH_CLASSIFICATION_CHANGED")
    evidence = {
        "url": RESEARCH_URL, "sha256": artifact.sha256, "fetched_at": artifact.fetched_at,
        "locator": RESEARCH_TITLE, "source_type": "original_research_repository_metadata",
        "publisher": "CAPES / Universidade Federal Fluminense",
    }
    enriched = deepcopy(exercises)
    for record in enriched:
        for classification in CLASSIFIED_GOVERNMENTS:
            classify_documented_government(record, classification, evidence)
    return enriched, evidence
