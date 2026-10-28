"""Read the explicitly current2023–2026 member cards, never similarly named news pages."""

import re
from html import unescape

from parsing.html import decode_html
from service.ingestion.contracts import IngestionError


def parse_directory_members(payload):
    html = decode_html(payload)
    if "Deputados Estaduais" not in html:
        raise IngestionError("ALRR_CURRENT_ROSTER_HEADING_MISSING")
    members = []
    for card in re.split(r'<div class="wpb_column vc_column_container vc_col-sm-3[^\"]*">', html)[
        1:
    ]:
        href = re.search(r'<a href="(https://al\.rr\.leg\.br/deputados/[^\"]+)"', card)
        if not href:
            continue
        captions = re.search(r"<h4[^>]*>(.*?)</h4>\s*<p[^>]*>(.*?)</p>", card, re.DOTALL)
        if not captions:
            raise IngestionError("ALRR_CURRENT_ROSTER_CARD_INVALID")
        name, political_party = (
            unescape(re.sub(r"<[^>]+>", "", value)).strip() for value in captions.groups()
        )
        members.append(
            {
                "provider_subject_id": href[1],
                "name": name,
                "political_party": political_party,
                "official_url": href[1],
            }
        )
    return members


def parse_current_roster(payload):
    members = parse_directory_members(payload)
    if len(members) != 24:
        raise IngestionError("ALRR_CURRENT_ROSTER_EXPECTED_24_MEMBERS")
    return members
