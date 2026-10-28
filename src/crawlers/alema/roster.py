"""Licensed deputies are explicitly separated by the publisher and must not inflate seats."""

import re
from html import unescape

from parsing.html import decode_html
from service.ingestion.contracts import IngestionError


def parse_current_roster(payload):
    html = decode_html(payload)
    marker = "<!-- Exibir deputados licenciados -->"
    if marker not in html:
        raise IngestionError("ALEMA_EXERCISE_LICENSED_BOUNDARY_MISSING")
    current = html.split(marker, 1)[0]
    members = []
    for url, name, political_party in re.findall(
        r'<h3 class="news-card-title"><a href="([^"]+)">([^<]+)</a></h3>\s*'
        r'<p class="news-card-chapeu">([^<]+)</p>',
        current,
    ):
        members.append(
            {
                "provider_subject_id": url,
                "name": unescape(name).strip(),
                "political_party": unescape(political_party).strip(),
                "official_url": url,
            }
        )
    if not members or len(members) > 42:
        raise IngestionError("ALEMA_CURRENT_ROSTER_UNEXPECTED_SIZE")
    return members
