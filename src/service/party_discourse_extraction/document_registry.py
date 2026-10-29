"""Finds the archived documents of the pilot parties from the discourse manifest."""

import json
import re
from dataclasses import dataclass
from pathlib import Path

ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass(frozen=True)
class PartyDocument:
    political_party: str
    sha256: str
    kind: str
    source_url: str
    document_date: str | None
    retrieved_on: str
    path: Path
    ocr_text_path: Path | None

    @property
    def short_hash(self) -> str:
        return self.sha256[:12]


def _ocr_path(discourse_root: Path, political_party: str, sha256: str) -> Path | None:
    ocr_directory = discourse_root / "parties" / political_party / "ocr"
    matches = sorted(ocr_directory.glob(f"*{sha256[:12]}.txt"))
    return matches[0] if matches else None


def _document(entry: dict, repo_root: Path, discourse_root: Path) -> PartyDocument | None:
    path = repo_root / entry.get("arquivo", "")
    if entry.get("status") != "obtained" or not path.is_file():
        return None
    date = entry.get("data_do_documento")
    return PartyDocument(
        political_party=entry["partido"],
        sha256=entry["sha256"],
        kind=entry["tipo"],
        source_url=entry["url"],
        document_date=date if isinstance(date, str) and ISO_DATE.match(date) else None,
        retrieved_on=entry["baixado_em"][:10],
        path=path,
        ocr_text_path=_ocr_path(discourse_root, entry["partido"], entry["sha256"]),
    )


def discover_documents(discourse_root: Path, repo_root: Path, parties: tuple[str, ...]):
    manifest = json.loads((discourse_root / "manifest.json").read_text())
    documents, seen = [], set()
    for entry in manifest["documents"]:
        if entry.get("partido") not in parties or entry.get("sha256") in seen:
            continue
        document = _document(entry, repo_root, discourse_root)
        if document is not None:
            seen.add(document.sha256)
            documents.append(document)
    return sorted(documents, key=lambda item: (item.political_party, item.sha256))
