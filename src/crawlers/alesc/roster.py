"""Read the current legislature directory, excluding repeated contact links."""

import re
from html import unescape

from parsing.html import decode_html
from service.ingestion.contracts import IngestionError


def parse_current_roster(payload):
    html = decode_html(payload)
    rows = []
    for card in re.findall(
        r'<article class="lab-card-team[^\"]*">(.*?)</article>', html, re.DOTALL
    ):
        href = re.search(r'<a href="(https://www\.alesc\.sc\.gov\.br/deputado/[^"]+)"', card)
        name = re.search(r'<h3 class="lab-title-news">([^<]+)</h3>', card)
        political_party = re.search(r'<span class="lab-button[^\"]*"[^>]*>([^<]+)</span>', card)
        if not href or not name or not political_party:
            raise IngestionError("ALESC_CURRENT_ROSTER_CARD_INVALID")
        rows.append(
            {
                "provider_subject_id": href[1],
                "name": unescape(name[1]).strip(),
                "political_party": unescape(political_party[1]).strip(),
                "official_url": href[1],
            }
        )
    if len(rows) != 40:
        raise IngestionError("ALESC_CURRENT_ROSTER_EXPECTED_40_MEMBERS")
    return rows
