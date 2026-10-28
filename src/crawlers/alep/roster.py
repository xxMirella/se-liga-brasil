"""Read every current member card, including the officers of the assembly."""

import re
from html import unescape

from parsing.html import decode_html
from service.ingestion.contracts import IngestionError


def parse_current_roster(payload):
    html = decode_html(payload)
    members = []
    for url, content in re.findall(
        r'<a\s+href="(https://www\.assembleia\.pr\.leg\.br/deputados/perfil/[^"]+)"[^>]*>(.*?)</a>',
        html,
        re.DOTALL,
    ):
        name = re.search(r"<h3[^>]*>\s*([^<]+)</h3>", content)
        political_party = re.search(
            r'<p class="text-gray-500 text-sm italic">\s*([^<]+)</p>', content
        )
        if not name or not political_party:
            continue
        members.append(
            {
                "provider_subject_id": url,
                "name": unescape(name[1]).strip(),
                "political_party": unescape(political_party[1]).strip(),
                "official_url": url,
            }
        )
    if len(members) != 54:
        raise IngestionError("ALEP_CURRENT_ROSTER_EXPECTED_54_MEMBERS")
    return members
