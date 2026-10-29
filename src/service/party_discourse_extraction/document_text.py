"""Plain text of an archived party document: digital PDF, HTML page or stored OCR output."""

import subprocess
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

MIN_DIGITAL_WORDS = 300
IGNORED_HTML_TAGS = frozenset(
    {"script", "style", "nav", "footer", "header", "noscript", "svg", "form", "aside"}
)


@dataclass(frozen=True)
class DocumentText:
    text: str
    origin: str  # digital_pdf | html | ocr


class _HtmlTextCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self._ignored_depth = 0
        self.paragraphs: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in IGNORED_HTML_TAGS:
            self._ignored_depth += 1

    def handle_endtag(self, tag):
        if tag in IGNORED_HTML_TAGS:
            self._ignored_depth = max(0, self._ignored_depth - 1)

    def handle_data(self, data):
        if not self._ignored_depth and data.strip():
            self.paragraphs.append(" ".join(data.split()))


def html_to_text(markup: str) -> str:
    collector = _HtmlTextCollector()
    collector.feed(markup)
    return "\n\n".join(collector.paragraphs)


def pdf_to_text(pdf_path: Path) -> str:
    completed = subprocess.run(  # noqa: S603
        ["pdftotext", str(pdf_path), "-"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.stdout


def load_document_text(path: Path, ocr_text_path: Path | None) -> DocumentText | None:
    """Text for the document, or None when a PDF has no text layer and no OCR exists yet."""
    if path.suffix.lower() in {".html", ".htm"}:
        return DocumentText(html_to_text(path.read_text(errors="ignore")), "html")
    digital = pdf_to_text(path)
    if len(digital.split()) >= MIN_DIGITAL_WORDS:
        return DocumentText(digital, "digital_pdf")
    if ocr_text_path is not None and ocr_text_path.is_file():
        return DocumentText(ocr_text_path.read_text(), "ocr")
    return None
