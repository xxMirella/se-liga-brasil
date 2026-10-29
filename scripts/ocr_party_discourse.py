"""OCR de PDFs escaneados de documentos partidários; o texto é bruto, não revisado, e fica à parte.

Lê um PDF já arquivado, converte cada página em imagem (pdftoppm) e roda o tesseract em português.
Grava `<saida>.txt` e `<saida>.json` (hash do PDF, versões das ferramentas, palavras por página).
Não acessa rede nem banco e não altera o PDF original.
"""

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

OCR_LANGUAGE = "por"
RENDER_DPI = "300"


def tool_version(command):
    completed = subprocess.run(command, capture_output=True, text=True, check=True)  # noqa: S603
    return (completed.stdout or completed.stderr).splitlines()[0].strip()


def render_pages(pdf_path, directory):
    prefix = directory / "page"
    subprocess.run(  # noqa: S603
        ["pdftoppm", "-r", RENDER_DPI, "-png", str(pdf_path), str(prefix)],  # noqa: S607
        check=True,
    )
    return sorted(directory.glob("page-*.png"))


def recognize_page(image_path):
    completed = subprocess.run(  # noqa: S603
        ["tesseract", str(image_path), "stdout", "-l", OCR_LANGUAGE, "--psm", "6"],  # noqa: S607
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout


def recognize_document(pdf_path):
    with tempfile.TemporaryDirectory() as workspace:
        images = render_pages(pdf_path, Path(workspace))
        return [recognize_page(image) for image in images]


def build_report(pdf_path, pages):
    return {
        "source_pdf": str(pdf_path),
        "source_sha256": hashlib.sha256(pdf_path.read_bytes()).hexdigest(),
        "ocr_engine": tool_version(["tesseract", "--version"]),  # noqa: S607
        "ocr_language": OCR_LANGUAGE,
        "render_dpi": int(RENDER_DPI),
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "pages": len(pages),
        "words_per_page": [len(page.split()) for page in pages],
        "review_status": "not_reviewed",
        "note": "Texto de OCR bruto; erros de reconhecimento são esperados. Não usar como citação.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("output_stem", type=Path, help="caminho sem extensão")
    arguments = parser.parse_args()
    if not arguments.pdf.is_file():
        sys.exit("PDF não encontrado")
    pages = recognize_document(arguments.pdf)
    arguments.output_stem.parent.mkdir(parents=True, exist_ok=True)
    arguments.output_stem.with_suffix(".txt").write_text("\f".join(pages))
    report = build_report(arguments.pdf, pages)
    arguments.output_stem.with_suffix(".json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2)
    )
    print(json.dumps({"pages": report["pages"], "words": sum(report["words_per_page"])}))


if __name__ == "__main__":
    main()
