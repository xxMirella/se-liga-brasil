"""Read the current Mato Grosso official parliament directory."""

import re
from html import unescape

from parsing.html import decode_html
from service.ingestion.contracts import IngestionError


def parse_current_roster(payload):
    pattern = (
        r'<span class="badge text-bg-secondary mb-1">\s*([^<]+)</span>\s*'
        r'<h6 class="card-title fw-semibold fs-14">([^<]+)</h6>\s*'
        r'<div class="d-grid">\s*<a href="/parlamento/deputados/(\d+)/perfil"'
    )
    members = [
        {
            "provider_subject_id": identifier,
            "name": unescape(name).strip(),
            "political_party": unescape(political_party).strip(),
            "official_url": f"https://www.al.mt.gov.br/parlamento/deputados/{identifier}/perfil",
        }
        for political_party, name, identifier in re.findall(pattern, decode_html(payload))
    ]
    if len(members) != 24:
        raise IngestionError("ALMT_CURRENT_ROSTER_EXPECTED_24_MEMBERS")
    return members
