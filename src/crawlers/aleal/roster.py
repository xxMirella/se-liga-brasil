"""Use AL's dedicated20th-legislature directory, excluding the explicit non-exercising section."""

import re
from html import unescape

from parsing.html import decode_html
from service.ingestion.contracts import IngestionError

BOUNDARY = "PARLAMENTARES ELEITOS MAS QUE NÃO ESTÃO EXERCENDO O MANDATO"


def parse_current_roster(payload):
    html = decode_html(payload)
    if "20ª LEGISLATURA" not in html or BOUNDARY not in html:
        raise IngestionError("ALEAL_CURRENT_EXERCISE_BOUNDARY_MISSING")
    current = html.split(BOUNDARY, 1)[0]
    members = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", current, re.DOTALL):
        profile = re.search(
            r'href="(https://sapl\.al\.al\.leg\.br/parlamentar/(\d+))"[^>]*>([^<]+)</a>', row
        )
        if not profile:
            continue
        political_party = re.search(r"<p>Partido:\s*([^<]+)</p>", row)
        if not political_party:
            raise IngestionError("ALEAL_CURRENT_ROSTER_PARTY_MISSING")
        label = unescape(political_party[1]).strip()
        members.append(
            {
                "provider_subject_id": profile[2],
                "name": unescape(profile[3]).strip(),
                "political_party": {"Progressistas": "PP", "União Brasil": "UNIÃO"}.get(
                    label, label
                ),
                "official_url": profile[1],
            }
        )
    if len(members) != 27:
        raise IngestionError("ALEAL_CURRENT_ROSTER_EXPECTED_27_MEMBERS")
    return members
