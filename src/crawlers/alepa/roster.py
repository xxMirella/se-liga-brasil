"""Read official Pará cards and their explicitly ordered server-supplied profile keys."""

import re
from html import unescape

from parsing.html import decode_html
from service.ingestion.contracts import IngestionError


def parse_current_roster(payload):
    html = decode_html(payload)
    key_match = re.search(r"'stateObject':\{'keys':\[([\d',]+)\]", html)
    cards = re.findall(
        r"<div class='card-info'><span>Deputad[oa]</span><span>([^<]+)</span><p>([^<]+)</p>",
        html,
    )
    if not key_match or len(cards) != 41:
        raise IngestionError("ALEPA_CURRENT_ROSTER_EXPECTED_41_MEMBERS")
    keys = re.findall(r"'(\d+)'", key_match[1])
    if len(keys) != len(cards) or len(set(keys)) != len(keys):
        raise IngestionError("ALEPA_CURRENT_ROSTER_PROFILE_KEYS_INVALID")
    return [
        {
            "provider_subject_id": identifier,
            "name": unescape(name).strip(),
            "political_party": "UNIÃO" if political_party == "UB" else unescape(political_party),
            "official_url": f"https://www.alepa.pa.gov.br/Institucional/Deputado/{identifier}",
        }
        for identifier, (name, political_party) in zip(keys, cards, strict=True)
    ]
