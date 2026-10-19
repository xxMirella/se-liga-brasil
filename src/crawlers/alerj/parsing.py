"""Extract bounded ALERJ page observations without network or database access."""

import re
from datetime import date
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urljoin

from crawlers.alerj.configuration import PORTAL_BASE
from parsing.html import decode_html
from service.ingestion.contracts import IngestionError

MONTHS = {
    name: number
    for number, name in enumerate(
        (
            "janeiro",
            "fevereiro",
            "março",
            "abril",
            "maio",
            "junho",
            "julho",
            "agosto",
            "setembro",
            "outubro",
            "novembro",
            "dezembro",
        ),
        start=1,
    )
}


class PageObservations(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text = []
        self.links = []
        self.anchor = None

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.anchor = [dict(attrs).get("href", ""), []]
        if tag in {"h1", "h2", "h3", "p", "div", "br"}:
            self.text.append("\n")

    def handle_data(self, data):
        self.text.append(data)
        if self.anchor is not None:
            self.anchor[1].append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.anchor is not None:
            href, parts = self.anchor
            self.links.append((href, " ".join("".join(parts).split())))
            self.anchor = None


def parse_page(payload):
    parser = PageObservations()
    parser.feed(decode_html(payload))
    return parser


def parse_roster(payload):
    page = parse_page(payload)
    members = {}
    for href, name in page.links:
        if name and href.startswith("/Deputados/PerfilDeputado/"):
            members[urljoin(PORTAL_BASE, href)] = name
    if not members or len(members) > 200:
        raise IngestionError("ALERJ_ROSTER_LAYOUT_CHANGED")
    return [{"url": url, "display_name": name} for url, name in members.items()]


def parse_profile(payload, expected_name):
    page = parse_page(payload)
    text = "\n".join(line.strip() for line in "".join(page.text).splitlines() if line.strip())
    birth = re.search(r"NASCIMENTO\s+(\d{1,2}) de (\w+) de (\d{4})", text)
    current = re.search(r"(\d+)[ºª] Legislatura \((\d{4}) [–-] (\d{4})\) - Atual", text)
    events = parse_affiliation_events(text)
    if not birth or not current or not events:
        raise IngestionError("ALERJ_PROFILE_LAYOUT_CHANGED")
    name = re.search(r"DEPUTAD[OA]\s+([^\n]+)", text)
    if name is None or name.group(1).casefold() != expected_name.casefold():
        raise IngestionError("ALERJ_PROFILE_NAME_MISMATCH")
    party = re.search(r'<div class="partido"><span>([^<]+)</span>', decode_html(payload))
    if party is None:
        raise IngestionError("ALERJ_CURRENT_PARTY_MISSING")
    day, month, year = birth.groups()
    return {
        "displayName": name.group(1),
        "politicalPartyAbbreviation": unescape(party.group(1)).strip(),
        "birthDate": date(int(year), MONTHS[month.lower()], int(day)).isoformat(),
        "legislatureKey": current.group(1),
        "legislatureStartsYear": int(current.group(2)),
        "legislatureEndsYear": int(current.group(3)),
        "affiliationEvents": events,
    }


def parse_affiliation_events(text):
    pattern = r"(Posse na ALERJ:|Troca de partido: Ingresso no)\s+(.+?) - Data (\d{2}/\d{2}/\d{4})"
    events = []
    for kind, abbreviation, starts in re.findall(pattern, text):
        day, month, year = map(int, starts.split("/"))
        events.append(
            {
                "eventKind": "appointment" if kind.startswith("Posse") else "entry",
                "politicalPartyAbbreviation": abbreviation.strip(),
                "startsOn": date(year, month, day).isoformat(),
            }
        )
    return events


class PayrollCatalog(PageObservations):
    def __init__(self):
        super().__init__()
        self.year = None
        self.month = None
        self.documents = []

    def handle_starttag(self, tag, attrs):
        super().handle_starttag(tag, attrs)
        attributes = dict(attrs)
        heading = attributes.get("id", "")
        if heading.startswith("heading-") and heading[8:].isdigit():
            self.year = int(heading[8:])
        href = attributes.get("href", "")
        if tag == "a" and href.startswith("/download-spic?file=") and self.year and self.month:
            self.documents.append((date(self.year, self.month, 1).isoformat(), href))

    def handle_data(self, data):
        super().handle_data(data)
        if data.strip().lower() in MONTHS:
            self.month = MONTHS[data.strip().lower()]


def latest_payroll_document(payload):
    from urllib.parse import parse_qs, urlsplit

    catalog = PayrollCatalog()
    catalog.feed(decode_html(payload))
    if not catalog.documents:
        raise IngestionError("ALERJ_PAYROLL_INDEX_LAYOUT_CHANGED")
    competence, href = max(catalog.documents)
    url = parse_qs(urlsplit(href).query).get("file", [None])[0]
    if url is None:
        raise IngestionError("ALERJ_PAYROLL_DOCUMENT_URL_MISSING")
    return competence, url
