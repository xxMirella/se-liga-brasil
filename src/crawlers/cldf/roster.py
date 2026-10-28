"""The homepage's current deputy carousel is separate from future election results."""

import re
from html import unescape
from urllib.parse import urljoin

from parsing.html import decode_html
from service.ingestion.contracts import IngestionError


def parse_current_roster(payload):
    html = decode_html(payload)
    if "Conheça os deputados" not in html:
        raise IngestionError("CLDF_CURRENT_ROSTER_HEADING_MISSING")
    members = {}
    for attributes, content in re.findall(r"<a\b([^>]+)>(.*?)</a>", html, re.DOTALL):
        name = re.search(r'<h3 class="deputado-nome[^\"]*"[^>]*>([^<]+)</h3>', content)
        political_party = re.search(r'<p class="deputado-partido[^\"]*"[^>]*>([^<]+)</p>', content)
        if not name or not political_party:
            continue
        href = re.search(r'href="([^"]+)"', attributes)
        if not href:
            raise IngestionError("CLDF_CURRENT_ROSTER_PROFILE_MISSING")
        url = urljoin("https://www.cl.df.gov.br/", unescape(href[1]))
        member = {
            "provider_subject_id": url,
            "name": unescape(name[1]).strip(),
            "political_party": unescape(political_party[1]).strip(),
            "official_url": url,
        }
        if url in members and members[url] != member:
            raise IngestionError("CLDF_CURRENT_ROSTER_CONFLICTING_MEMBER")
        members[url] = member
    if not members or len(members) > 50:
        raise IngestionError("CLDF_CURRENT_ROSTER_LAYOUT_CHANGED")
    return list(members.values())
