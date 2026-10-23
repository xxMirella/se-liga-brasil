"""An accessory document's principal comes from an explicit official API field."""

import pytest

from crawlers.camara.legislative_normalization import normalize_legislative_detail
from service.ingestion.contracts import IngestionError

DOCUMENT = "https://dadosabertos.camara.leg.br/api/v2/proposicoes/11"
PRINCIPAL = "https://dadosabertos.camara.leg.br/api/v2/proposicoes/10"


def detail(**values):
    return {"uri": DOCUMENT, "siglaTipo": "PRL", "numero": 1, "ano": 0,
            "ementa": "Parecer que cita PL 20/2024 e PL 30/2024."} | values


def test_only_explicit_principal_field_supplies_the_parent_relationship():
    assert normalize_legislative_detail(detail())["principalProposition"] is None
    result = normalize_legislative_detail(detail(uriPropPrincipal=PRINCIPAL))
    assert result["principalProposition"] == PRINCIPAL
    assert result["officialKey"] == DOCUMENT and result["year"] is None


@pytest.mark.parametrize("principal", [DOCUMENT, "https://example.com/proposicoes/10",
                                      PRINCIPAL + "?other=1"])
def test_invalid_principal_relationship_is_rejected_before_ingestion(principal):
    with pytest.raises(IngestionError, match="PRINCIPAL_PROPOSITION"):
        normalize_legislative_detail(detail(uriPropPrincipal=principal))
