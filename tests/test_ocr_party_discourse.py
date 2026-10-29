import importlib.util
import json
import subprocess
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def completed(stdout="", stderr=""):
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr=stderr)


def test_recognize_page_calls_tesseract_in_portuguese(monkeypatch, tmp_path):
    ocr = load_script("ocr_party_discourse")
    calls = []

    def fake_run(command, **options):
        calls.append(command)
        return completed(stdout="Art. 1º O partido")

    monkeypatch.setattr(ocr.subprocess, "run", fake_run)
    assert ocr.recognize_page(tmp_path / "page-1.png") == "Art. 1º O partido"
    assert calls[0][0] == "tesseract" and "por" in calls[0]


def test_build_report_marks_text_as_not_reviewed_and_ties_it_to_the_pdf_hash(monkeypatch, tmp_path):
    ocr = load_script("ocr_party_discourse")
    pdf_path = tmp_path / "estatuto.pdf"
    pdf_path.write_bytes(b"%PDF fixture")
    monkeypatch.setattr(ocr, "tool_version", lambda command: "tesseract fixture")
    report = ocr.build_report(pdf_path, ["um dois tres", "quatro"])
    assert report["review_status"] == "not_reviewed"
    assert report["words_per_page"] == [3, 1]
    assert len(report["source_sha256"]) == 64
    json.dumps(report)


def test_recognize_document_reads_pages_in_filename_order(monkeypatch, tmp_path):
    ocr = load_script("ocr_party_discourse")
    images = [tmp_path / "page-01.png", tmp_path / "page-02.png"]
    monkeypatch.setattr(ocr, "render_pages", lambda pdf, directory: images)
    monkeypatch.setattr(ocr, "recognize_page", lambda image: image.stem)
    assert ocr.recognize_document(tmp_path / "x.pdf") == ["page-01", "page-02"]


def test_text_poor_pdf_is_detected_by_words_per_page(monkeypatch):
    batch = load_script("ocr_pending_party_documents")
    monkeypatch.setattr(batch, "page_count", lambda pdf: 10)
    monkeypatch.setattr(batch, "embedded_word_count", lambda pdf: 880)  # só carimbo
    assert batch.is_text_poor(Path("x.pdf"))
    monkeypatch.setattr(batch, "embedded_word_count", lambda pdf: 5000)
    assert not batch.is_text_poor(Path("x.pdf"))


def test_pending_documents_skips_duplicates_by_hash(monkeypatch, tmp_path):
    batch = load_script("ocr_pending_party_documents")
    pdf_path = tmp_path / "a.pdf"
    pdf_path.write_bytes(b"x")
    rows = [("PDT", "a" * 64, pdf_path), ("PDT", "a" * 64, pdf_path)]
    monkeypatch.setattr(batch, "manifest_pdfs", lambda: iter(rows))
    monkeypatch.setattr(batch, "is_text_poor", lambda pdf: True)
    assert len(list(batch.pending_documents())) == 1
