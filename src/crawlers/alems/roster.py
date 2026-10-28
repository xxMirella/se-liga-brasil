"""Read Mato Grosso do Sul's official contemporary deputies grouped by party."""

import re
from html import unescape

from parsing.html import decode_html
from service.ingestion.contracts import IngestionError


def parse_current_roster(payload):
    members = []
    groups = re.split(r'<div class="party"\s*>', decode_html(payload))[1:]
    for group in groups:
        heading = re.search(r'<div class="party-name"[^>]*>([^<]+)</div>', group)
        if not heading:
            raise IngestionError("ALEMS_PARTY_DIRECTORY_HEADING_MISSING")
        for identifier, content in re.findall(
            r'<a class="party-deputy" href="/Deputados/Visualizar/(\d+)">(.*?)</a>',
            group,
            re.DOTALL,
        ):
            name = re.search(r'<div class="">([^<]+)</div>', content)
            if not name:
                raise IngestionError("ALEMS_PARTY_DIRECTORY_MEMBER_NAME_MISSING")
            members.append(
                {
                    "provider_subject_id": identifier,
                    "name": unescape(name[1]).strip(),
                    "political_party": unescape(heading[1]).strip(),
                    "official_url": f"https://al.ms.gov.br/Deputados/Visualizar/{identifier}",
                }
            )
    if len(members) != 24:
        raise IngestionError("ALEMS_CURRENT_ROSTER_EXPECTED_24_MEMBERS")
    return members
