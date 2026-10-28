"""Read the official current legislature's full roster, including party labels."""

import re
from html import unescape
from urllib.parse import urljoin

from crawlers.alerj.configuration import PORTAL_BASE
from parsing.html import decode_html
from service.ingestion.contracts import IngestionError


def parse_current_roster(payload):
    html = decode_html(payload)
    declared = re.search(
        r"Legislatura\s*\((\d{4})\s*[–-]\s*(\d{4})\).*?<span>\s*(\d+) deputados", html, re.DOTALL
    )
    if not declared:
        raise IngestionError("ALERJ_CURRENT_ROSTER_HEADING_MISSING")
    rows = []
    for fragment in re.split(r'<div\s+class="controle_deputado(?:\s+[^\"]*)?"\s*>', html)[1:]:
        political_party = re.search(r'<div\s+class="partido">([^<]+)</div>', fragment)
        member = re.search(r'<div\s+class="nome">\s*<a href="([^"]+)">([^<]+)</a>', fragment)
        if not political_party or not member:
            raise IngestionError("ALERJ_CURRENT_ROSTER_CARD_INVALID")
        rows.append(
            {
                "provider_subject_id": member[1].split("?")[0].rsplit("/", 1)[-1],
                "name": unescape(member[2]).strip(),
                "political_party": unescape(political_party[1]).strip(),
                "official_url": urljoin(PORTAL_BASE, member[1]),
                "legislature_start_year": int(declared[1]),
                "legislature_end_year": int(declared[2]),
            }
        )
    if len(rows) != int(declared[3]):
        raise IngestionError("ALERJ_ROSTER_DECLARED_TOTAL_MISMATCH")
    return rows
