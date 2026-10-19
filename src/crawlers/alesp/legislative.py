"""Stream verified ALESP document proceedings; final approval is never inferred."""

from datetime import date

from crawlers.alesp.local_records import xml_rows
from normalization.scalars import normalize_date
from service.acquisition.downloader import download_resource
from service.ingestion.contracts import DownloadBudget, IngestionError, Resource
from storage.files import hash_content

PROCEEDINGS_URL = (
    "https://www.al.sp.gov.br/repositorioDados/processo_legislativo/documento_andamentos.zip"
)
SUPPORTED_DOMAINS = frozenset({"proceedings"})


def legislative_capability(domain, start, end):
    validate_interval(start, end)
    return {
        "institution": "alesp",
        "domain": domain,
        "requested_start": start.isoformat(),
        "requested_end": end.isoformat(),
        "status": "supported" if domain in SUPPORTED_DOMAINS else "unsupported",
        "source_coverage_start": None,
        "source_coverage_end": None,
        "historical_completeness": "not_verified",
    }


def collect_proceedings(configuration, client, document_keys, start, end, budget=None):
    """One cached bulk resource serves every selected document in this interval."""
    validate_interval(start, end)
    document_keys = frozenset(str(key) for key in document_keys)
    if not document_keys:
        return iter(()), None
    resource = Resource(
        "alesp-document-proceedings",
        "ALESP document proceedings",
        PROCEEDINGS_URL,
        "proceedings",
        start.year,
        "alesp-document-proceedings",
        "SP",
        ".zip",
    )
    artifact = download_resource(resource, configuration, client, budget or DownloadBudget())
    return selected_proceedings(artifact.path, document_keys, start, end), artifact


def validate_interval(start, end):
    if not isinstance(start, date) or not isinstance(end, date) or start > end:
        raise IngestionError("INVALID_LEGISLATIVE_INTERVAL")


def selected_proceedings(path, document_keys, start, end):
    """O(export rows); memory is one XML record plus the requested document index."""
    for row in xml_rows(path, "DocumentoAndamento"):
        if row.get("IdDocumento") not in document_keys:
            continue
        event = normalize_proceeding(row)
        if start.isoformat() <= event["occurred_on"] <= end.isoformat():
            yield event


def normalize_proceeding(row):
    required = ("IdDocumento", "Data", "NrOrdem", "IdEtapa", "Descricao")
    if any(not row.get(key) for key in required):
        raise IngestionError("ALESP_PROCEEDING_SCHEMA_CHANGED")
    occurred_on = normalize_date(row["Data"])
    key = "|".join(
        row.get(key, "")
        for key in (
            "IdDocumento",
            "Data",
            "NrOrdem",
            "IdEtapa",
            "IdTpAndamento",
            "IdComissao",
        )
    )
    return {
        "source_key": hash_content(key),
        "proposition_source_key": row["IdDocumento"],
        "occurred_on": occurred_on,
        "event_kind": "proceeding",
        "description": row["Descricao"],
        "stage": row.get("NmEtapa"),
        "body": row.get("SiglaComissao"),
        "source_type": row.get("TpAndamento"),
        "final_outcome": None,
    }
