"""Pure SPLEGIS normalization; collective results never imply individual votes."""

from crawlers.cmsp.parsing import child_elements, element_text
from normalization.identity import normalize_person_name
from normalization.scalars import normalize_date, normalize_digits, normalize_text, normalize_year
from service.ingestion.contracts import IngestionError


def source_date(value):
    text = normalize_text(value)
    if text is None:
        return None
    date_format = "%Y-%m-%d" if len(text) == 10 and text[4] == "-" else "%d/%m/%Y"
    return normalize_date(text, date_format=date_format)


def normalize_authors(project):
    names = {}
    for author in child_elements(project, "Autores", "Autor"):
        name = normalize_text(element_text(author, "Nome"), required=True, max_length=300)
        names[name] = None
    return list(names)


def normalize_project(project, expected_year):
    year = normalize_year(element_text(project, "Ano"), minimum=1948, maximum=2200)
    if year != expected_year:
        raise IngestionError("CMSP_PARTITION_YEAR_MISMATCH")
    kind = normalize_text(element_text(project, "Tipo"), required=True, max_length=30)
    number = normalize_digits(element_text(project, "Numero"))
    if int(number) <= 0:
        raise IngestionError("CMSP_INVALID_PROPOSITION_NUMBER")
    return {
        "officialKey": f"{kind}:{number}:{year}",
        "kind": kind,
        "number": number,
        "year": year,
        "title": f"{kind} {number}/{year}",
        "summary": normalize_text(element_text(project, "Ementa"), max_length=30000),
        "introducedOn": source_date(element_text(project, "Data")),
        "authorNames": normalize_authors(project),
        "verifiedAuthors": [],
        "subscribersAreNotAutomaticallyAuthors": True,
        "deliberationObservations": [
            {
                "description": normalize_text(element_text(item, "Resultado"), required=True),
                "occurredAt": None,
                "individualVote": None,
            }
            for item in child_elements(project, "Deliberacoes", "Deliberacao")
        ],
        "normReference": {
            name: normalize_text(element_text(project, name))
            for name in ("TipoNorma", "NumeroNorma", "AnoNorma", "DataNorma")
        },
        "phaseObserved": normalize_text(element_text(project, "Fase")),
        "currentStatus": "unknown",
    }


def attach_reviewed_authors(record, bindings, artifact_sha256):
    """Bindings originate in reviewed personal evidence, never an automatic name join."""
    for name in record["authorNames"]:
        binding = bindings.get(normalize_person_name(name))
        if binding is None:
            continue
        if binding.artifact_sha256 != artifact_sha256:
            raise IngestionError("CMSP_REVIEWED_ARTIFACT_CHANGED")
        record["verifiedAuthors"].append(
            {
                "personId": str(binding.person_id),
                "role": "author",
                "evidenceReference": binding.evidence_reference,
                "identityMethod": binding.method,
            }
        )
    return record
