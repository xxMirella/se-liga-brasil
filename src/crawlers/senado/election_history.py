"""Parse elected candidates separately from dated exercise and affiliation records."""

import re
from html.parser import HTMLParser

from storage.files import hash_content


class SenateElectionHistoryParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.year = None
        self.first_republic = False
        self.is_winner_section = False
        self.capture_tag = None
        self.capture_parts = []
        self.capture_is_party_badge = False
        self.pending = None
        self.records = []

    def handle_starttag(self, tag, attributes):
        if tag in {"h2", "h3", "h4", "span"} and self.capture_tag is None:
            self.capture_tag = tag
            self.capture_parts = []
            style = dict(attributes).get("style", "")
            self.capture_is_party_badge = tag != "span" or (
                "#eff6ff" in style or (
                    "border-radius: 999px" in style and "font-weight: 900" in style
                ) or (
                    "border-radius: 12px" in style and "font-weight: 600" in style
                    and "padding: 6px 12px" in style
                )
            )

    def handle_data(self, text):
        if self.capture_tag:
            self.capture_parts.append(text)

    def handle_endtag(self, tag):
        if tag != self.capture_tag:
            return
        text = " ".join("".join(self.capture_parts).split())
        self.capture_tag = None
        if self.capture_is_party_badge:
            self.consume_text(tag, text)

    def consume_text(self, tag, text):
        consumers = {"h2": self.consume_year, "h3": self.consume_candidate,
                     "h4": self.consume_subheading, "span": self.consume_political_label}
        consumers[tag](text)

    def consume_year(self, text):
        self.flush_candidate()
        self.first_republic = "Primeira República" in text
        self.year = int(text) if re.fullmatch(r"\d{4}", text) else None
        self.is_winner_section = self.year is not None

    def consume_candidate(self, text):
        if not self.year or not self.is_winner_section:
            return
        self.flush_candidate()
        self.pending = {"name": text.rstrip(" 🔄🏅"), "election_year": self.year,
                        "political_party_literal": None}

    def consume_political_label(self, text):
        if not self.pending or self.pending["political_party_literal"] is not None:
            return
        if is_political_label(text):
            self.pending["political_party_literal"] = text

    def consume_subheading(self, text):
        self.flush_candidate()
        if self.first_republic and re.fullmatch(r"\d{4}", text):
            self.year = int(text)
            self.is_winner_section = True
        elif "Demais candidatos" in text:
            self.is_winner_section = False

    def flush_candidate(self):
        if self.pending:
            self.records.append(self.pending)
            self.pending = None


def is_political_label(text):
    return bool(re.fullmatch(r"[^\W\d_][\w /().-]{0,40}", text)) and (
        not any(word in text.casefold() for word in ("voto", "eleição", "fonte"))
    )


def parse_senate_election_history(html, territory_code, evidence):
    parser = SenateElectionHistoryParser()
    parser.feed(html)
    parser.flush_candidate()
    result = []
    for row in parser.records:
        literal = row["political_party_literal"]
        interpretation = "multiple_labels" if literal and "/" in literal else (
            "single_label" if literal else "not_reported"
        )
        result.append({**row, "territory_code": territory_code,
                       "source_event_id": f"senado:eleicao:{territory_code}:"
                                          f"{row['election_year']}:{hash_content(row['name'])}",
                       "date_precision": "year", "canonical_person_id": None,
                       "political_party_interpretation": interpretation,
                       "evidence": {**evidence, "locator": str(row["election_year"])}})
    return result
