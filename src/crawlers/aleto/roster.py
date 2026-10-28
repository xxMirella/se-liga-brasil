"""Read the official current Tocantins common profile directory."""

import re
from html import unescape
from urllib.parse import urljoin

from parsing.html import decode_html
from service.ingestion.contracts import IngestionError


def parse_current_roster(payload):
    members = []
    for card in decode_html(payload).split('<div class="quadro-deputado-container"')[1:]:
        captions = re.search(r"<h3>([^<]+)</h3>\s*<h5>([^<]+)</h5>", card)
        profile = re.search(r'<a href="(/perfil/parlamentar/[^\"]+/(\d+))"', card)
        if not captions or not profile:
            raise IngestionError("ALETO_CURRENT_ROSTER_CARD_INVALID")
        political_party = unescape(captions[2]).strip()
        members.append(
            {
                "provider_subject_id": profile[2],
                "name": unescape(captions[1]).strip(),
                "political_party": "UNIÃO" if political_party == "UB" else political_party,
                "official_url": urljoin("https://www.al.to.leg.br/", profile[1]),
            }
        )
    if len(members) != 24:
        raise IngestionError("ALETO_CURRENT_ROSTER_EXPECTED_24_MEMBERS")
    return members
