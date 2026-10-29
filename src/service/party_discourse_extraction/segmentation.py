"""Splits a document into passages that keep articles and sections together."""

import re
from dataclasses import dataclass

MAX_SEGMENT_CHARACTERS = 4000
MIN_SEGMENT_CHARACTERS = 200
HEADING_PATTERN = re.compile(r"^(art\.?\s*\d+|cap[ií]tulo|se[cç][aã]o|t[ií]tulo)\b", re.IGNORECASE)
SENTENCE_BOUNDARY = re.compile(r"(?<=[.;:!?])\s+")


@dataclass(frozen=True)
class Segment:
    segment_id: str
    ordinal: int
    heading: str
    text: str


def split_blocks(text: str) -> list[str]:
    """Paragraph blocks; wrapped lines are joined, an article heading always starts a block."""
    blocks: list[str] = []
    for paragraph in re.split(r"\n\s*\n", text):
        lines = [" ".join(line.split()) for line in paragraph.splitlines() if line.strip()]
        current: list[str] = []
        for line in lines:
            if HEADING_PATTERN.match(line) and current:
                blocks.append(" ".join(current))
                current = []
            current.append(line)
        if current:
            blocks.append(" ".join(current))
    return blocks


def _split_long_block(block: str) -> list[str]:
    pieces, current = [], ""
    for sentence in SENTENCE_BOUNDARY.split(block):
        if current and len(current) + len(sentence) + 1 > MAX_SEGMENT_CHARACTERS:
            pieces.append(current)
            current = ""
        current = f"{current} {sentence}".strip()
    if current:
        pieces.append(current)
    return pieces


def pack_blocks(blocks: list[str]) -> list[str]:
    packed, current = [], ""
    for block in blocks:
        for piece in _split_long_block(block):
            if current and len(current) + len(piece) + 2 > MAX_SEGMENT_CHARACTERS:
                packed.append(current)
                current = ""
            current = f"{current}\n\n{piece}".strip()
    if current:
        packed.append(current)
    return packed


def segment_document(text: str, document_key: str) -> list[Segment]:
    segments = []
    for ordinal, body in enumerate(pack_blocks(split_blocks(text)), start=1):
        if len(body) < MIN_SEGMENT_CHARACTERS:
            continue
        heading = body.split("\n", 1)[0][:80]
        segments.append(Segment(f"{document_key}-{ordinal:04d}", ordinal, heading, body))
    return segments
