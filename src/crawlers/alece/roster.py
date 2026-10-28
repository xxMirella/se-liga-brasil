"""Ceará explicitly marks licensed titulares in HTML while listing active substitutes separately."""

import re
from html import unescape

from parsing.html import decode_html
from service.ingestion.contracts import IngestionError


def parse_current_roster(payload):
    members = []
    cards = re.split(r'<div\s+class="deputado_card([^\"]*)"', decode_html(payload))
    licensed = 0
    for css, card in zip(cards[1::2], cards[2::2], strict=True):
        if "licenciado" in css.split():
            licensed += 1
            continue
        name = re.search(r'class="deputado_card--nome[^\"]*"><a href="([^\"]+)">\s*([^<]+)', card)
        political_party = re.search(r'class="deputado_card--partido[^\"]*">\s*([^<]+)', card)
        if not name or not political_party:
            raise IngestionError("ALECE_CURRENT_ROSTER_CARD_INVALID")
        members.append(
            {
                "provider_subject_id": name[1],
                "name": unescape(name[2]).strip(),
                "political_party": unescape(political_party[1]).strip(),
                "official_url": name[1],
            }
        )
    if len(members) != 46 or not licensed:
        raise IngestionError("ALECE_CURRENT_ROSTER_EXPECTED_46_AND_LICENSE_MARKERS")
    return members
