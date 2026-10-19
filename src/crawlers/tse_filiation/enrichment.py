"""Keep affiliation gaps open until a public, identifiable source is validated."""

SOURCE_VALIDATION_RETRY_SECONDS = 7 * 24 * 60 * 60
DOMAIN_FIELDS = frozenset({"current_political_party", "political_party_affiliation_history"})
SOURCE_EVIDENCE_URLS = (
    "https://www.tse.jus.br/partidos/filiacao-partidaria/filiacao-partidaria",
    "https://dadosabertos.tse.jus.br/dataset/delegados-partidarios",
    "https://www.tse.jus.br/legislacao/codigo-eleitoral/normas-editadas-pelo-tse/"
    "resolucao-no-23-596-de-20-de-agosto-de-2019-2013-brasilia-df-1",
)


def collect_tse_filiation(connection, storage, people, fields=None) -> dict:
    """Report unavailable coverage without remote calls or invented affiliation facts.

    ``people`` is an orchestrator mapping of internal person UUID to requested fields.
    Uniform connector arguments are accepted without touching connection or storage.
    One bounded source-level failure prevents one failing request per person.
    """
    if not people:
        return {"status": "completed", "target_people": 0, "failures": []}
    requested_fields = set(fields or ())
    if fields is None:
        for person_fields in people.values():
            requested_fields.update(person_fields)
    return {
        "status": "blocked",
        "target_people": len(people),
        "requested_fields": sorted(requested_fields),
        "unsupported_fields": sorted(requested_fields - DOMAIN_FIELDS),
        "requires_source_validation": True,
        "source_evidence_urls": list(SOURCE_EVIDENCE_URLS),
        "network_requests": 0,
        "ingested_facts": 0,
        "failures": [
            {
                "code": "PUBLIC_NOMINAL_AFFILIATION_SOURCE_NOT_VALIDATED",
                "retry_after_seconds": SOURCE_VALIDATION_RETRY_SECONDS,
            }
        ],
    }
