"""Parse the official current-roster HTML report, excluding personal contact columns."""

from collections import Counter
from html.parser import HTMLParser


class SenateRosterReportParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.members = []
        self.cells = []
        self.fragments = []
        self.in_roster_table = False
        self.in_cell = False

    def handle_starttag(self, tag, attrs):
        if tag == "table" and "linha-senador" in dict(attrs).get("class", "").split():
            self.in_roster_table = True
            self.cells = []
        if tag == "td" and self.in_roster_table:
            self.in_cell = True
            self.fragments = []

    def handle_data(self, data):
        if self.in_cell:
            self.fragments.append(data)

    def handle_endtag(self, tag):
        if tag == "td" and self.in_cell:
            self.cells.append(" ".join("".join(self.fragments).split()))
            self.in_cell = False
        if tag == "table" and self.in_roster_table:
            if len(self.cells) != 10:
                raise ValueError("SENATE_ROSTER_REPORT_COLUMNS_CHANGED")
            name, political_party, uf, capacity, mandate = self.cells[:5]
            self.members.append({"name": name, "political_party": political_party,
                                 "uf": uf, "capacity": capacity, "mandate": mandate})
            self.in_roster_table = False


def parse_current_roster_report(content):
    parser = SenateRosterReportParser()
    parser.feed(content)
    members = parser.members
    if len(members) != 81 or len({(row["name"], row["uf"]) for row in members}) != 81:
        raise ValueError("SENATE_ROSTER_REPORT_EXPECTED_81_UNIQUE_MEMBERS")
    uf_counts = Counter(row["uf"] for row in members)
    if len(uf_counts) != 27 or set(uf_counts.values()) != {3}:
        raise ValueError("SENATE_ROSTER_REPORT_EXPECTED_THREE_SEATS_PER_UF")
    return members
