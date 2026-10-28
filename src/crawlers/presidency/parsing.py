"""Normalize explicit official year ranges without inventing dates or party affiliation."""

import re
from html.parser import HTMLParser

from parsing.html import decode_html
from service.ingestion.contracts import IngestionError
from storage.files import hash_content

YEAR_HEADING = re.compile(r"(?m)^\s*(18\d{2}|19\d{2})\s*[-–]\s*(19\d{2}|18\d{2}):"
                          r"\s*([^\n]+?)\s+-\s+")


class PresidentialPageText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.suppressed = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.suppressed += 1
        if tag in {"p", "br", "h1", "h2", "div", "tr"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.suppressed = max(0, self.suppressed - 1)

    def handle_data(self, data):
        if not self.suppressed:
            self.parts.append(data)


def extract_chronology_text(payload):
    parser = PresidentialPageText()
    parser.feed(decode_html(payload))
    text = "".join(parser.parts)
    if "Você não tem permissão" in text or "não possui permissão" in text:
        raise IngestionError("PRESIDENCY_ACCESS_DENIED_DOCUMENT")
    return text


def parse_first_republic_chronology(payload, *, source_url, sha256, fetched_at):
    text = extract_chronology_text(payload)
    headings = list(YEAR_HEADING.finditer(text))
    if not headings:
        raise IngestionError("PRESIDENCY_CHRONOLOGY_NOT_FOUND")
    records = []
    for heading in headings:
        start_year, end_year = int(heading[1]), int(heading[2])
        if not 1889 <= start_year <= end_year <= 1930:
            raise IngestionError("PRESIDENCY_CHRONOLOGY_INVALID_RANGE")
        name = " ".join(heading[3].split())
        records.append({
            "institution_code": "presidency", "territory_code": "BR",
            "person_id": "camara-chronology:" + hash_content(name)[:24], "name": name,
            "year_start": start_year, "year_end": end_year, "date_precision": "year",
            "starts_on": None, "ends_before": None,
            "political_party_code": None, "political_party": None,
            "political_party_status": "unknown", "canonical_person_id": None,
            "coverage": "historical_chronology_partial",
            "evidence": [{"url": source_url, "sha256": sha256, "fetched_at": fetched_at,
                          "locator": heading[0].strip()}],
        })
    return records
