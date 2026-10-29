"""OCR em lote, em sequência, dos PDFs partidários já ingeridos que não têm camada de texto útil.

Lê `discourse/manifest.json` (somente leitura), escolhe PDFs com menos de 150 palavras por página
(sem texto ou só carimbo), remove duplicatas por sha256, pula o que já tem OCR e grava o resultado
em `parties/<PARTIDO>/ocr/<stem>.txt|json` mais um índice `discourse/ocr_index.json`.
Não altera os PDFs nem acessa rede ou banco; só `--register` escreve no manifest.
Sequencial de propósito: o tesseract já usa a CPU e vários ao mesmo tempo só disputam núcleos.
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ocr_party_discourse import build_report, recognize_document  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DISCOURSE = PROJECT_ROOT / "data/political-orientation/party-model/discourse"
MINIMUM_WORDS_PER_PAGE = 150


def page_count(pdf_path):
    info = subprocess.run(  # noqa: S603
        ["pdfinfo", str(pdf_path)],  # noqa: S607
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    match = re.search(r"Pages:\s+(\d+)", info)
    return int(match.group(1)) if match else 0


def embedded_word_count(pdf_path):
    text = subprocess.run(  # noqa: S603
        ["pdftotext", str(pdf_path), "-"],  # noqa: S607
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return len(text.split())


def is_text_poor(pdf_path):
    pages = page_count(pdf_path)
    return pages > 0 and embedded_word_count(pdf_path) / pages < MINIMUM_WORDS_PER_PAGE


def manifest_pdfs():
    manifest = json.loads((DISCOURSE / "manifest.json").read_text())
    for document in manifest["documents"]:
        archived = document.get("arquivo") or ""
        if archived.lower().endswith(".pdf") and document.get("status") == "obtained":
            yield document["partido"], document["sha256"], PROJECT_ROOT / archived


def pending_documents():
    seen = set()
    for political_party, sha256, pdf_path in manifest_pdfs():
        if sha256 in seen or not pdf_path.is_file():
            continue
        seen.add(sha256)
        if is_text_poor(pdf_path):
            yield political_party, sha256, pdf_path


def output_stem(political_party, sha256):
    return DISCOURSE / "parties" / political_party / "ocr" / f"estatuto-{sha256[:12]}"


def run_one(political_party, sha256, pdf_path):
    stem = output_stem(political_party, sha256)
    if stem.with_suffix(".json").exists():
        return {"political_party": political_party, "sha256": sha256, "status": "already_done"}
    pages = recognize_document(pdf_path)
    stem.parent.mkdir(parents=True, exist_ok=True)
    stem.with_suffix(".txt").write_text("\f".join(pages))
    report = build_report(pdf_path, pages)
    stem.with_suffix(".json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    return {
        "political_party": political_party,
        "sha256": sha256,
        "status": "done",
        "pages": report["pages"],
    }


def write_json_atomically(path, payload):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    temporary.replace(path)


def ocr_reference(report_path):
    report = json.loads(report_path.read_text())
    return {
        "ocr_text_file": str(report_path.with_suffix(".txt").relative_to(PROJECT_ROOT)),
        "ocr_engine": report["ocr_engine"],
        "ocr_language": report["ocr_language"],
        "ocr_review_status": report["review_status"],
        "ocr_source_sha256": report["source_sha256"],
    }


def ocr_references_by_sha256():
    references = {}
    for report_path in DISCOURSE.glob("parties/*/ocr/*.json"):
        reference = ocr_reference(report_path)
        references[reference["ocr_source_sha256"]] = reference
    return references


def register_ocr_in_manifest():
    """Liga cada documento ao texto de OCR pelo sha256 do PDF; rode com o manifest parado."""
    manifest_path = DISCOURSE / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    references = ocr_references_by_sha256()
    linked = 0
    for document in manifest["documents"]:
        reference = references.get(document.get("sha256"))
        if reference:
            document.update(reference)
            linked += 1
    write_json_atomically(manifest_path, manifest)
    return linked


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="só lista o que seria processado")
    parser.add_argument(
        "--register", action="store_true", help="liga o OCR existente ao manifest e sai"
    )
    arguments = parser.parse_args()
    if arguments.register:
        print(json.dumps({"documents_linked": register_ocr_in_manifest()}))
        return
    pending = list(pending_documents())
    if arguments.list:
        for political_party, sha256, pdf_path in pending:
            print(political_party, sha256[:12], page_count(pdf_path), pdf_path.name[:80])
        return
    results = []
    for political_party, sha256, pdf_path in pending:
        results.append(run_one(political_party, sha256, pdf_path))
        print(json.dumps(results[-1], ensure_ascii=False), flush=True)
    (DISCOURSE / "ocr_index.json").write_text(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
