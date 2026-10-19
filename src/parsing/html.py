"""Standard-library HTML extraction without network or domain rules."""

from html.parser import HTMLParser


def decode_html(payload: bytes) -> str:
    try:
        return payload.decode("utf-8-sig")
    except UnicodeDecodeError:
        return payload.decode("cp1252")


class HtmlLinksParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []

    def handle_starttag(self, tag, attrs) -> None:
        attributes = dict(attrs)
        if tag == "a" and attributes.get("href"):
            self.links.append(attributes["href"])


class HtmlTableParser(HTMLParser):
    def __init__(self, table_id: str | None) -> None:
        super().__init__(convert_charrefs=True)
        self.table_id = table_id
        self.active = False
        self.rows: list[list[str]] = []
        self.row: list[str] = []
        self.cell: list[str] | None = None
        self.text: list[str] = []

    def handle_starttag(self, tag, attrs) -> None:
        if tag == "table" and (self.table_id is None or dict(attrs).get("id") == self.table_id):
            self.active = True
        if not self.active:
            return
        if tag == "tr":
            self.row = []
        if tag in {"td", "th"}:
            self.cell = []
        if tag == "br" and self.cell is not None:
            self.cell.append(" ")

    def handle_data(self, data) -> None:
        self.text.append(data)
        if self.active and self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag) -> None:
        if not self.active:
            return
        if tag in {"td", "th"} and self.cell is not None:
            self.row.append(" ".join("".join(self.cell).split()))
            self.cell = None
        if tag == "tr" and self.row:
            self.rows.append(self.row)
        if tag == "table":
            self.active = False
