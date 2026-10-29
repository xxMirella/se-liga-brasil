"""Explicit self-declared labels, quoted verbatim from the party's own archived document.

Keyword extractions (`temas`) are unreviewed (rubric_pending) and stay out. Only quotes that a
curated review file points at are converted, and each quote must exist verbatim in the archive;
the stance is a reading of the quote, recorded as not yet reviewed by a person.
"""

from datetime import date

from service.party_orientation_evidence.records import PROOF_PRIMARY, evidence_record
from service.party_orientation_model.contracts import (
    DIMENSION_OVERALL,
    LAYER_DISCOURSE,
    PartyModelContractError,
    normalize_party_key,
)

INDICATOR = "self_declared_position"
ATTRIBUTION = "party_official_document"


def archived_quotes(party_document: dict) -> list[tuple[dict, str]]:
    """(document, quote) for every quote the extractor kept, labels and themes alike."""
    pairs = []
    for document in party_document.get("documentos_obtidos", []):
        pairs.extend((document, item["trecho"]) for item in document["rotulo_declarado_candidatos"])
        for theme_items in document["temas"].values():
            pairs.extend((document, item["trecho"]) for item in theme_items)
    return pairs


def find_quote(party_document: dict, url: str, quote_prefix: str) -> tuple[dict, str]:
    for document, quote in archived_quotes(party_document):
        if document["url"] == url and quote.startswith(quote_prefix):
            return document, quote
    raise PartyModelContractError("DISCOURSE_QUOTE_NOT_IN_ARCHIVE", quote_prefix[:40])


def self_declaration_records(reviews: list[dict], party_documents: dict[str, dict]) -> list[dict]:
    records = []
    for review in reviews:
        party = review["political_party"]
        document, quote = find_quote(
            party_documents[normalize_party_key(party)],
            review["document_url"],
            review["quote_prefix"],
        )
        records.append(
            evidence_record(
                evidence_id=f"discourse:{normalize_party_key(party)}:{review['review_id']}",
                political_party=party,
                layer=LAYER_DISCOURSE,
                dimension=DIMENSION_OVERALL,
                indicator_id=INDICATOR,
                stance=float(review["stance"]),
                source_id=f"party-document-{document['sha256'][:12]}",
                source_url=document["url"],
                source_date=date.fromisoformat(review["source_date"]),
                year_start=review["year"],
                year_end=review["year"],
                proof_level=PROOF_PRIMARY,
                attribution_basis=ATTRIBUTION,
                description=f"Citação literal do documento do partido: «{quote[:240]}». "
                f"Leitura: {review['reading']}. Leitura automatizada, sem revisão humana.",
            )
        )
    return records


def discourse_conversion_notes() -> list[str]:
    return [
        "Fora do cálculo: extração por palavra-chave (`temas`) não revisada (rubric_pending) e "
        "documentos escaneados (PDT, PRD) sem OCR.",
        "Autodeclarações explícitas entram só como dimensão 'overall' (indicador "
        "self_declared_position): servem para o contraste discurso x ação, não para o escore.",
    ]
