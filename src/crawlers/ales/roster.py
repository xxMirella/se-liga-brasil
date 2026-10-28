"""Read the common current Espírito Santo deputy directory."""

import re
from html import unescape
from urllib.parse import urljoin

from parsing.html import decode_html
from service.ingestion.contracts import IngestionError


def parse_current_roster(payload):
    members = []
    for href, content in re.findall(
        r'<a\s+href="([^\"]+)"[^>]*>(.*?)</a>', decode_html(payload), re.DOTALL
    ):
        name = re.search(r'<div class="nomeDeputadoLista">([^<]+)</div>', content)
        if not name:
            continue
        political_party = re.search(r"<strong>([^<]+)</strong>", content)
        if not political_party or not href.startswith("/Deputado/"):
            raise IngestionError("ALES_CURRENT_ROSTER_CARD_INVALID")
        url = urljoin("https://www.al.es.gov.br/", unescape(href))
        members.append(
            {
                "provider_subject_id": url,
                "name": unescape(name[1]).strip(),
                "political_party": unescape(political_party[1]).strip(),
                "official_url": url,
            }
        )
    if len(members) != 30:
        raise IngestionError("ALES_CURRENT_ROSTER_EXPECTED_30_MEMBERS")
    return members
