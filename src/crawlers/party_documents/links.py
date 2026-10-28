"""Read explicit official directory links, without interpreting party names as ideology."""

from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit


class DocumentLinks(HTMLParser):
    def __init__(self, base_url):
        super().__init__()
        self.base_url, self.links, self.current, self.parts = base_url, [], None, []

    def handle_starttag(self, tag, attributes):
        if tag == "a":
            self.current, self.parts = dict(attributes).get("href"), []

    def handle_data(self, data):
        if self.current:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.current:
            self.links.append({"url": urljoin(self.base_url, self.current),
                               "text": " ".join(" ".join(self.parts).split())})
            self.current, self.parts = None, []


def parsed_document_links(content, base_url):
    parser = DocumentLinks(base_url)
    parser.feed(content)
    return parser.links


def current_statute_link(content, base_url):
    for link in parsed_document_links(content, base_url):
        if "estatuto do partido" not in link["text"].casefold():
            continue
        if urlsplit(link["url"]).hostname not in {
            "www.tse.jus.br", "www.justicaeleitoral.jus.br",
        }:
            continue
        return link
    return None
