"""Read all24profile-directory tooltips; the portal warns updates may lag during migration."""

import re
from html import unescape

from parsing.html import decode_html
from service.ingestion.contracts import IngestionError

LABELS = {
    "REPUBLICANO": "REPUBLICANOS",
    "PARTIDO VERDE - PV": "PV",
    "PV (PARTIDO VERDE)": "PV",
    "REDE SUSTENTABILIDADE - REDE": "REDE",
    "UNIÃO BRASIL (UNIÃO)": "UNIÃO",
}


def parse_current_roster(payload):
    html = decode_html(payload)
    members = []
    for identifier, tooltip in re.findall(
        r'<a href="pagina.php\?pg=exibir_parlamentar&iddeputado=(\d+)" '
        r'onmouseover="Tip\(\'(.*?)\', WIDTH',
        html,
        re.DOTALL,
    ):
        name = re.search(r"<b>Dep\.</b>\s*(.*?)<br>", tooltip)
        political_party = re.search(r"<b>Partido:</b>\s*(.*?)<br>", tooltip)
        if not name or not political_party:
            raise IngestionError("ALAP_DIRECTORY_TOOLTIP_SCHEMA_CHANGED")
        label = unescape(political_party[1]).strip()
        members.append(
            {
                "provider_subject_id": identifier,
                "name": unescape(name[1]).strip(),
                "political_party": LABELS.get(label, label),
                "official_url": "https://www.al.ap.leg.br/pagina.php?pg=exibir_parlamentar"
                f"&iddeputado={identifier}",
            }
        )
    if len(members) != 24:
        raise IngestionError("ALAP_DIRECTORY_EXPECTED_24_PROFILES")
    if "as informações estão sendo migradas e atualizadas" not in html:
        raise IngestionError("ALAP_DIRECTORY_MIGRATION_WARNING_CHANGED")
    return members
