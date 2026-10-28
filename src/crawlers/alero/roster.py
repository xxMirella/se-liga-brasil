"""Reconcile Rondônia's common directory with its individual official party fields."""

import re
from html import unescape
from urllib.parse import urljoin

from parsing.html import decode_html
from service.ingestion.contracts import IngestionError

PARTY_NAMES = {
    "Partido Liberal": "PL",
    "Partido Progressista - PP": "PP",
    "Partido dos Trabalhadores": "PT",
    "Partido Social Democrático": "PSD",
    "Partido Progressistas": "PP",
    "Progressistas": "PP",
    "União Brasil": "UNIÃO",
    "Republicanos": "REPUBLICANOS",
    "Movimento Democrático Brasileiro": "MDB",
    "Podemos": "PODE",
    "Partido da Social Democracia Brasileira": "PSDB",
    "Partido Socialista Brasileiro": "PSB",
    "Partido Renovação Democrática": "PRD",
    "Solidariedade": "SOLIDARIEDADE",
}


def parse_current_roster(payload):
    links = re.findall(
        r'<a href="(/deputados/perfil/[^\"]+)">\s*'
        r'<div class="font-bold[^\"]*">\s*([^<]+)</div>',
        decode_html(payload),
    )
    members = [
        {
            "provider_subject_id": path.rsplit("/", 1)[-1],
            "name": unescape(name).strip(),
            "political_party": None,
            "official_url": urljoin("https://www.al.ro.leg.br/", path),
        }
        for path, name in links
    ]
    if len(members) != 24:
        raise IngestionError("ALERO_CURRENT_ROSTER_EXPECTED_24_MEMBERS")
    return members


def parse_profile_party(payload, expected_name):
    html = decode_html(payload)
    heading = re.search(r'<h1 class="text-xl font-bold text-sky-700">([^<]+)</h1>', html)
    party = re.search(r'<p class="text-gray-500 text-xs">([^<]+)</p>', html)
    if not heading or unescape(heading[1]).strip() != expected_name or not party:
        raise IngestionError("ALERO_OFFICIAL_PROFILE_IDENTITY_OR_PARTY_MISSING")
    label = unescape(party[1]).strip()
    return PARTY_NAMES.get(label, label)
