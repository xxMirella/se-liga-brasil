"""Deduplicate photo/name view modes against the declared official roster total."""

import re
from html import unescape
from urllib.parse import urljoin

from parsing.html import decode_html
from service.ingestion.contracts import IngestionError


def parse_current_roster(payload):
    html = decode_html(payload)
    declared = re.search(r'<span class="numbers">(\d+)</span> Deputados do', html)
    if not declared:
        raise IngestionError("ALEPE_ROSTER_DECLARED_TOTAL_MISSING")
    members = {}
    for href, content in re.findall(
        r"<a href=['\"]([^'\"]+)['\"] class=\"parlamentares-list-a\">(.*?)</a>", html, re.DOTALL
    ):
        name = re.search(r'<h2 class="title parlamentares-nome">([^<]+)</h2>', content)
        political_party = re.search(
            r'<span class="subtitle parlamentares-partido">([^<]+)</span>', content
        )
        if not name or not political_party:
            raise IngestionError("ALEPE_ROSTER_CARD_INVALID")
        url = urljoin("https://www.alepe.pe.gov.br/", unescape(href))
        member = {
            "provider_subject_id": url,
            "name": unescape(name[1]).strip(),
            "political_party": unescape(political_party[1]).strip(),
            "official_url": url,
        }
        if url in members and members[url] != member:
            raise IngestionError("ALEPE_ROSTER_VIEW_MODES_CONFLICT")
        members[url] = member
    if len(members) != int(declared[1]):
        raise IngestionError("ALEPE_ROSTER_DECLARED_TOTAL_MISMATCH")
    return list(members.values())
