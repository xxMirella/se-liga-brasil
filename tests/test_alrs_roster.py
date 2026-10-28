import html
import json

import pytest

from crawlers.alrs.roster import parse_attendance, parse_current_roster
from service.ingestion.contracts import IngestionError


def attendance_document(rows):
    return ''.join(f"<article data-item='{html.escape(json.dumps(row), quote=True)}'></article>"
                   for row in rows)


def source_bundle():
    rows = [{"codProponente": str(number), "nomeProponente": f"Pessoa {number}",
             "ano": 2026, "mesNumerico": 10, "presenca": 1} for number in range(55)]
    profiles = {str(number): f'<h2 class="title deputado-name">Dep. Pessoa {number}</h2>'
                '<p>Partido: <strong>PT</strong></p>' for number in range(55)}
    return {"attendance_html": attendance_document(rows), "profiles": profiles}, rows


def test_reconciles_only_matching_official_presence_and_profile_identities():
    bundle, _ = source_bundle()
    members = parse_current_roster(json.dumps(bundle))
    assert len(members) == 55
    assert members[0]["political_party"] == "PT"
    bundle["profiles"]["0"] = bundle["profiles"]["1"]
    with pytest.raises(IngestionError, match="IDENTITY_MISMATCH"):
        parse_current_roster(json.dumps(bundle))


@pytest.mark.parametrize("mutation", ["duplicate", "no_presence", "mixed_period", "missing"])
def test_rejects_ambiguous_or_unconfirmed_monthly_members(mutation):
    _, rows = source_bundle()
    if mutation == "duplicate":
        rows[0]["codProponente"] = rows[1]["codProponente"]
    elif mutation == "no_presence":
        rows[0]["presenca"] = 0
    elif mutation == "mixed_period":
        rows[0]["mesNumerico"] = 9
    else:
        rows.pop()
    with pytest.raises(IngestionError):
        parse_attendance(attendance_document(rows))
