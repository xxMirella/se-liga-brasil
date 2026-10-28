"""Read presidential party metadata from reviewed external-mandate fields, never page badges."""

import re

from crawlers.presidency.parsing import extract_chronology_text
from service.ingestion.contracts import IngestionError

PRESIDENTIAL_MANDATE = re.compile(
    r"^Presidente da República, Partido:\s*(?P<abbreviation>[A-Za-z0-9]+),\s*"
    r"Período:\s*(?P<start>\d{4})(?:\s+a\s+(?P<end>\d{4}))?\.?$",
)
REVIEWED_CAMARA_PROFILES = (
    ("204", "139289", "LUIZ INÁCIO LULA DA SILVA", "PT", "Partido dos Trabalhadores"),
    ("198", "131036", "JOSÉ SARNEY", "PMDB", "Partido do Movimento Democrático Brasileiro"),
    ("200", "132129", "FERNANDO COLLOR", "PRN", "Partido da Reconstrução Nacional"),
    ("182", "2876", "JUSCELINO KUBITSCHEK", "PSD", "Partido Social Democrático"),
)


def parse_camara_presidential_mandates(payload, *, subject):
    text = " ".join(extract_chronology_text(payload).split())
    if subject not in text:
        raise IngestionError("CAMARA_HISTORICAL_PRESIDENT_SUBJECT_CHANGED")
    section = text.partition("Mandatos Externos:")[2]
    section = re.split(r"Atividades\s|Estudos\s|Registros\s|Obras\s", section, maxsplit=1)[0]
    observations = []
    for item in section.split(";"):
        matched = PRESIDENTIAL_MANDATE.fullmatch(item.strip())
        if matched:
            observations.append({
                "year_start": int(matched["start"]),
                "year_end": int(matched["end"]) if matched["end"] else None,
                "political_party_abbreviation": matched["abbreviation"],
                "source_period_precision": "year", "locator": item.strip(),
            })
    if not observations:
        raise IngestionError("CAMARA_PRESIDENTIAL_PARTY_MANDATE_NOT_FOUND")
    return observations
