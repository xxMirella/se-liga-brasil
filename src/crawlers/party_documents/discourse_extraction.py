"""Extract traceable literal excerpts from already archived party documents."""

import re
import subprocess
from pathlib import Path

from crawlers.party_documents.discourse_sources import (
    ARTICLE_PATTERN,
    EXCERPTS_PER_THEME,
    LABEL_PATTERN,
    MAX_EXCERPT_CHARS,
    THEMES,
)

ROOT = Path(__file__).resolve().parents[3]


def html_to_text(content: bytes) -> str:
    html = content.decode("utf-8", errors="replace")
    html = re.sub(r"(?is)<(script|style|noscript|svg|nav|footer|header).*?</\1>", " ", html)
    html = re.sub(r"(?i)</(p|div|li|h\d|br|tr)>|<br\s*/?>", "\n\n", html)
    text = re.sub(r"<[^>]+>", " ", html)
    import html as html_lib

    return re.sub(r"[ \t]+", " ", html_lib.unescape(text))


def pages_of(entry: dict) -> list[str]:
    """Texto por pagina (PDF) ou por bloco unico (HTML)."""
    path = ROOT / entry["arquivo"]
    if path.suffix == ".pdf":
        result = subprocess.run(
            ["pdftotext", "-layout", str(path), "-"], capture_output=True, check=True
        )
        return result.stdout.decode("utf-8", errors="replace").split("\f")
    return [html_to_text(path.read_bytes())]


def nearest_article(page_text: str, position: int) -> str | None:
    found = ARTICLE_PATTERN.findall(page_text[:position])
    return found[-1] if found else None


def paragraphs(page_text: str) -> list[tuple[int, str]]:
    result, offset = [], 0
    for block in re.split(r"\n\s*\n", page_text):
        clean = re.sub(r"\s+", " ", block).strip()
        if len(clean) > 40:
            result.append((page_text.find(block, offset), clean))
        offset += len(block)
    return result


def locator(entry: dict, page_index: int, page_text: str, position: int) -> str:
    where = (
        f"p. {page_index + 1}"
        if entry["arquivo"].endswith(".pdf")
        else "pagina HTML (sem paginacao)"
    )
    article = nearest_article(page_text, max(position, 0))
    return f"{where}; {article}" if article else where


def document_paragraphs(document_pages):
    for page_index, page_text in enumerate(document_pages):
        for position, paragraph in paragraphs(page_text):
            yield page_index, page_text, position, paragraph


def extract_matches(entry: dict, pattern: re.Pattern[str], limit: int, *, document_pages=None):
    if limit <= 0:
        return []
    if document_pages is None:
        document_pages = pages_of(entry)
    found, seen = [], set()
    for page_index, page_text, position, paragraph in document_paragraphs(document_pages):
        if not pattern.search(paragraph) or paragraph[:80] in seen:
            continue
        seen.add(paragraph[:80])
        found.append(
            {
                "trecho": paragraph[:MAX_EXCERPT_CHARS],
                "localizador": locator(entry, page_index, page_text, position),
            }
        )
        if len(found) >= limit:
            break
    return found


def extract_discourse(entry: dict) -> dict:
    document_pages = pages_of(entry)
    themes = {
        name: extract_matches(
            entry,
            re.compile(regex, re.IGNORECASE),
            EXCERPTS_PER_THEME,
            document_pages=document_pages,
        )
        for name, regex in THEMES.items()
    }
    return {
        "sha256": entry["sha256"],
        "tipo": entry["tipo"],
        "url": entry["url"],
        "data_do_documento": entry["data_do_documento"],
        "arquivo": entry["arquivo"],
        "rotulo_declarado_candidatos": extract_matches(
            entry, LABEL_PATTERN, 5, document_pages=document_pages
        ),
        "temas": themes,
        "aviso_extracao": None
        if any(themes.values())
        else (
            "nenhum trecho correspondente: pode não haver palavras pesquisadas; "
            "PDF sem camada de texto requer"
            " OCR; HTML pode depender de JavaScript. Ausência não comprova orientação."
        ),
    }
