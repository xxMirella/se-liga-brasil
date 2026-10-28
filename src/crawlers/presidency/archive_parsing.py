"""Parse only linked Archive Nacional biographies and their presidential date headings."""

import re
from datetime import date
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

from parsing.html import decode_html
from service.ingestion.contracts import IngestionError

ARCHIVE_CATALOG_URL = (
    "https://presidentes.an.gov.br/index.php/centro-de-referencia-de-acervos-"
    "presidenciais/assuntos/biografias"
)
ARTICLE_PATH = re.compile(r"/biografias/(\d+)-[a-z0-9-]+$")
PERIOD = re.compile(r"^(\d{1,2}\.\d{1,2}\.\d{4})(?:\s*[-–]\s*"
                    r"(\d{1,2}\.\d{1,2}\.\d{4}))?$")


class ArchiveBiographyPage(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.headings = []
        self.links = []
        self.heading = None
        self.anchor = None

    def handle_starttag(self, tag, attrs):
        if tag in {"h1", "h2", "h3", "h4"}:
            self.heading = [tag, []]
        if tag == "br" and self.heading is not None:
            self.heading[1].append("\n")
        if tag == "a":
            self.anchor = [dict(attrs).get("href", ""), []]

    def handle_data(self, data):
        if self.heading is not None:
            self.heading[1].append(data)
        if self.anchor is not None:
            self.anchor[1].append(data)

    def handle_endtag(self, tag):
        if self.heading is not None and tag == self.heading[0]:
            self.headings.append((tag, "".join(self.heading[1]).strip()))
            self.heading = None
        if tag == "a" and self.anchor is not None:
            self.links.append((self.anchor[0], " ".join("".join(self.anchor[1]).split())))
            self.anchor = None


def parse_archive_page(payload):
    page = ArchiveBiographyPage()
    page.feed(decode_html(payload))
    return page


def discover_archive_biographies(payload, *, limit=45):
    if type(limit) is not int or not 1 <= limit <= 45:
        raise ValueError("PRESIDENTIAL_CATALOG_LIMIT_INVALID")
    pages = {}
    for href, name in parse_archive_page(payload).links:
        url = urljoin(ARCHIVE_CATALOG_URL, href)
        parsed = urlsplit(url)
        trusted = parsed.scheme == "https" and parsed.hostname == "presidentes.an.gov.br"
        if trusted and name and ARTICLE_PATH.search(parsed.path):
            pages[url] = name
    if not pages or len(pages) > limit:
        raise IngestionError("PRESIDENTIAL_CATALOG_MISSING_OR_OVER_LIMIT")
    return list(pages.items())


def archive_date(value):
    day, month, year = map(int, value.split("."))
    return date(year, month, day)


def parse_archive_exercises(payload, artifact, *, observed_on):
    page = parse_archive_page(payload)
    names = [text for tag, text in page.headings if tag == "h1" and text]
    article = ARTICLE_PATH.search(urlsplit(artifact.resource.url).path)
    if len(names) != 1 or article is None:
        raise IngestionError("PRESIDENTIAL_BIOGRAPHY_IDENTITY_HEADING_REQUIRED")
    periods = [line.strip() for tag, text in page.headings if tag != "h1"
               for line in text.splitlines() if PERIOD.fullmatch(line.strip())]
    records = [archive_exercise(names[0], article[1], period, artifact, observed_on)
               for period in periods]
    if len({row["exercise_id"] for row in records}) != len(records):
        raise IngestionError("PRESIDENTIAL_BIOGRAPHY_DUPLICATE_PERIOD")
    return records


def archive_exercise(name, article_id, period, artifact, observed_on):
    matched = PERIOD.fullmatch(period)
    starts_on = archive_date(matched[1])
    ends_before = archive_date(matched[2]) if matched[2] else None
    if starts_on < date(1889, 11, 15) or starts_on > observed_on:
        raise IngestionError("PRESIDENTIAL_EXERCISE_DATE_OUT_OF_RANGE")
    if ends_before and ends_before <= starts_on:
        raise IngestionError("PRESIDENTIAL_EXERCISE_END_NOT_AFTER_START")
    if ends_before and (ends_before - starts_on).days > 20 * 366:
        raise IngestionError("PRESIDENTIAL_HEADING_MAY_BE_LIFESPAN_NOT_EXERCISE")
    identifier = "arquivo-nacional-president:" + article_id
    return {
        "institution_code": "presidency", "territory_code": "BR", "name": name,
        "person_id": identifier, "exercise_id": identifier + ":" + str(starts_on),
        "starts_on": str(starts_on), "ends_before": str(ends_before) if ends_before else None,
        "date_precision": "day", "boundary_semantics": "transfer_dates_as_published",
        "observed_through": str(observed_on), "canonical_person_id": None,
        "political_party_code": None, "political_party": None,
        "political_party_status": "unknown", "source_url": artifact.resource.url,
        "exercise_capacity": "collective_junta" if name.startswith("Junta ") else "president",
        "evidence": [{"url": artifact.resource.url, "sha256": artifact.sha256,
                      "fetched_at": artifact.fetched_at, "locator": period}],
    }
