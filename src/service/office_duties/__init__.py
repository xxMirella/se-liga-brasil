"""Read-only reviewed descriptions of legislative office responsibilities."""

from dataclasses import asdict
from datetime import date

from service.office_duties.catalog import CATALOG_VERSION, CATALOGS, REVIEWED_ON

LIMITATIONS = (
    "Competências coletivas da instituição não são "
    "obrigações individuais de produzir quantidade de atos.",
    "Ausência de registros não demonstra inatividade nem descumprimento de atribuições.",
    "Aprovação coletiva, autoria, relatoria e voto individual são fatos distintos.",
    "Data de revisão do catálogo não é data de entrada em vigor da norma.",
)


def get_office_duties(office_kind: str, jurisdiction: str, *, as_of: date) -> dict:
    """Return only a date-reviewed catalog; unsupported dates never borrow today's rules."""
    if type(as_of) is not date:
        raise ValueError("INVALID_DUTIES_DATE")
    if not isinstance(office_kind, str) or not isinstance(jurisdiction, str):
        raise ValueError("INVALID_DUTIES_SCOPE")
    catalog = CATALOGS.get((office_kind, jurisdiction))
    response = {
        "office_kind": office_kind,
        "jurisdiction": jurisdiction,
        "as_of": as_of.isoformat(),
        "catalog_version": CATALOG_VERSION,
        "reviewed_on": REVIEWED_ON.isoformat(),
        "legal_valid_from": None,
        "legal_valid_through": None,
        "status": "not_cataloged",
        "items": [],
        "limitations": list(LIMITATIONS),
    }
    if catalog is None:
        return response
    response["limitations"].extend(catalog.limitations)
    if as_of != REVIEWED_ON:
        response["status"] = "historical_not_verified" if as_of < REVIEWED_ON else "review_required"
        return response
    response["status"] = "reviewed_summary"
    response["items"] = [asdict(item) for item in catalog.items]
    return response
