"""Arquiva estatutos/programas partidarios e extrai a camada DISCURSO/AUTODECLARACAO.

Subcomandos:
  fetch          baixa as fontes publicas listadas em PARTY_SOURCES (User-Agent identificavel,
                 intervalo educado, sem qualquer contorno de bloqueio) e reconstroi os JSON.
  ingest-manual  le PDFs/HTML em discourse/manual/ (nome: SIGLA__tipo__AAAA-MM-DD.ext),
                 calcula sha256, atualiza o manifest e reconstroi os JSON.
  build          reconstroi apenas os party-discourse.json a partir do manifest.

Registra apenas o que o partido diz (autodeclaracao). Nao conclui lado politico.
Sem rubrica em party-model/rubric.json, as dimensoes ficam 'rubric_pending'.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from crawlers.party_documents.discourse_extraction import extract_discourse  # noqa: E402
from crawlers.party_documents.discourse_sources import ALL_PARTIES, PARTY_SOURCES  # noqa: E402

BASE = ROOT / "data/political-orientation/party-model"
DISCOURSE = BASE / "discourse"
MANUAL = DISCOURSE / "manual"
MANIFEST = DISCOURSE / "manifest.json"
RUBRIC = BASE / "rubric.json"
USER_AGENT = "SeLigaBrasilResearch/1.0 (pesquisa academica)"
TSE_LIST_URL = (
    "https://www.tse.jus.br/partidos/partidos-registrados-no-tse"  # hardcode-ok: fonte TSE
)
TSE_BLOCK_REASON = (
    "TSE bloqueia acesso automatizado (HTTP 403 Akamai); documento deve ser baixado manualmente"
)
POLITE_DELAY_SECONDS = 1.5
MAX_DOCUMENT_BYTES = 15 * 1024 * 1024


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def load_manifest() -> dict:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {"schema": "party-discourse-manifest/2", "documents": []}


def save_manifest(manifest: dict) -> None:
    manifest["updated_on"] = now_iso()
    temporary = MANIFEST.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(MANIFEST)  # atomic rename: concurrent readers never see a partial file


def guess_document_date(*texts: str) -> str | None:
    for text in texts:
        match = re.search(r"(20\d{2})[-_/](\d{2})[-_/](\d{2})", text)
        if match:
            return "-".join(match.groups())
        match = re.search(r"(\d{2})[-_.](\d{2})[-_.](20\d{2})", text)
        if match:
            return f"{match.group(3)}-{match.group(2)}-{match.group(1)}"
    for text in texts:
        match = re.search(r"/(20\d{2})/(\d{2})/", text)
        if match:
            return f"{match.group(1)}-{match.group(2)} (data de upload na URL, nao do documento)"
    return None


def download(url: str) -> tuple[int | None, bytes, str, str]:
    """Retorna (status, bytes, content_type, motivo_erro)."""
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept-Language": "pt-BR"}
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            content = response.read(MAX_DOCUMENT_BYTES + 1)
            if len(content) > MAX_DOCUMENT_BYTES:
                return None, b"", "", "documento excede limite de 15 MiB"
            return response.status, content, response.headers.get("Content-Type", ""), ""
    except urllib.error.HTTPError as error:
        return error.code, b"", "", f"HTTP {error.code}"
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        return None, b"", "", f"falha de rede: {error}"


def file_extension(content: bytes, content_type: str) -> str:
    if content[:5] == b"%PDF-":
        return "pdf"
    return "html" if "html" in content_type.lower() or b"<html" in content[:2000].lower() else "bin"


def store_raw(party: str, kind: str, content: bytes, extension: str) -> Path:
    digest = sha256_bytes(content)
    target = DISCOURSE / "raw" / party / f"{kind}-{digest[:12]}.{extension}"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return target


def register_document(manifest: dict, entry: dict) -> None:
    key = (entry["partido"], entry["tipo"], entry["url"])
    manifest["documents"] = [
        d for d in manifest["documents"] if (d["partido"], d["tipo"], d["url"]) != key
    ]
    manifest["documents"].append(entry)


def cached_document_is_valid(manifest, political_party, kind, url):
    for entry in manifest["documents"]:
        if (entry["partido"], entry["tipo"], entry["url"]) != (political_party, kind, url):
            continue
        if entry.get("status") != "obtained" or not entry.get("arquivo"):
            return False
        path = ROOT / entry["arquivo"]
        return path.is_file() and sha256_bytes(path.read_bytes()) == entry.get("sha256")
    return False


def fetch_source(manifest: dict, party: str, kind: str, url: str) -> None:
    if cached_document_is_valid(manifest, party, kind, url):
        print(f"{party:14} {kind:24} cached")
        return
    status, content, content_type, error = download(url)
    entry = {
        "url": url,
        "partido": party,
        "tipo": kind,
        "data_do_documento": guess_document_date(url),
        "baixado_em": None,
        "sha256": None,
        "arquivo": None,
        "status": "unavailable",
        "motivo": error,
    }
    if status == 200 and content:
        path = store_raw(party, kind, content, file_extension(content, content_type))
        entry.update(
            baixado_em=now_iso(),
            sha256=sha256_bytes(content),
            arquivo=str(path.relative_to(ROOT)),
            status="obtained",
            motivo="",
        )
    elif status == 403 and "tse.jus.br" in url:
        entry["motivo"] = TSE_BLOCK_REASON
    register_document(manifest, entry)
    print(f"{party:14} {kind:24} {entry['status']:11} {entry['motivo']}")
    time.sleep(POLITE_DELAY_SECONDS)


def rubric_state() -> dict:
    if RUBRIC.exists():
        return {
            "status": "rubric_available_not_applied_by_this_script",
            "path": str(RUBRIC.relative_to(ROOT)),
        }
    return {"status": "rubric_pending"}


def build_party_file(party: str, documents: list[dict]) -> None:
    obtained = [d for d in documents if d["status"] == "obtained"]
    payload = {
        "schema": "party-discourse/1",
        "partido": party,
        "gerado_em": now_iso(),
        "camada": "autodeclaracao (discurso); nenhuma conclusao sobre lado politico",
        "rubrica": {"economica": rubric_state(), "sociocultural": rubric_state()},
        "documentos_obtidos": [extract_discourse(d) for d in obtained],
        "documentos_indisponiveis": [
            {"tipo": d["tipo"], "url": d["url"], "motivo": d["motivo"]}
            for d in documents
            if d["status"] != "obtained"
        ],
        "versoes_do_estatuto": [
            {"data": d["data_do_documento"], "sha256": d["sha256"], "url": d["url"]}
            for d in obtained
            if d["tipo"] == "estatuto"
        ],
        "historico_siglas_fusoes": (
            "nao extraido automaticamente; requer fonte documental (ver docs/p"
            "artidos-discurso-autodeclaracao.md)"
        ),
        "limites": [
            (
                "Trechos sao correspondencias por palavra-chave, nao interpretacao"
                "; leitura humana e necessaria."
            ),
            (
                "Rotulo declarado so vale se o trecho candidato for uma autodefini"
                "cao literal; ausencia nao implica centro."
            ),
            (
                "Pagina HTML nao tem paginacao; localizador de artigo e a ultima o"
                "correncia 'Art.' anterior ao trecho."
            ),
            "Discurso nao comprova comportamento (votos, governo).",
        ],
    }
    target = DISCOURSE / "parties" / party
    target.mkdir(parents=True, exist_ok=True)
    (target / "party-discourse.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def build_all(manifest: dict) -> None:
    by_party: dict[str, list[dict]] = {}
    for document in manifest["documents"]:
        if document.get("partido"):
            by_party.setdefault(document["partido"], []).append(document)
    for party, documents in sorted(by_party.items()):
        if any(d["status"] == "obtained" for d in documents):
            build_party_file(party, documents)


def ingest_manual(manifest: dict) -> None:
    MANUAL.mkdir(parents=True, exist_ok=True)
    for path in sorted(
        p for p in MANUAL.iterdir() if p.suffix.lower() in {".pdf", ".html", ".htm"}
    ):
        parts = path.stem.split("__")
        if len(parts) < 2:
            print(f"ignorado (nome fora do padrao SIGLA__tipo__AAAA-MM-DD): {path.name}")
            continue
        content = path.read_bytes()
        entry = {
            "url": f"manual:{path.name}",
            "partido": parts[0],
            "tipo": parts[1],
            "data_do_documento": parts[2] if len(parts) > 2 else None,
            "baixado_em": now_iso(),
            "sha256": sha256_bytes(content),
            "arquivo": str(path.relative_to(ROOT)),
            "status": "obtained",
            "motivo": "",
            "origem": "download manual (TSE ou outra fonte oficial)",
        }
        register_document(manifest, entry)
        print(f"manual: {path.name} -> {entry['sha256'][:12]}")


def write_manual_checklist() -> None:
    MANUAL.mkdir(parents=True, exist_ok=True)
    checklist = {
        "instrucao": (
            "Baixe estatuto e programa de cada partido na pagina do TSE e salv"
            "e aqui como SIGLA__estatuto__AAAA-MM-DD.pdf ou SIGLA__programa__A"
            "AAA-MM-DD.pdf; depois rode: python3 scripts/archive_party_discour"
            "se.py ingest-manual"
        ),
        "pagina_tse": TSE_LIST_URL,
        "observacao": (
            "Consulte primeiro manifest.json e inventário para reutilizar originais "
            "com hash validado. Acesso automatizado pode retornar403; navegação "
            "normal pelo TSE permite verificar links e datas sem contornar bloqueios."
        ),
        "documentos": [
            {
                "partido": p,
                "tipo": t,
                "arquivo_sugerido": f"{p}__{t}__AAAA-MM-DD.pdf",
                "pagina_tse": TSE_LIST_URL,
            }
            for p in ALL_PARTIES
            for t in ("estatuto", "programa")
        ],
    }
    (MANUAL / "CHECKLIST.json").write_text(
        json.dumps(checklist, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def main(argv: list[str]) -> int:
    command = argv[1] if len(argv) > 1 else "build"
    manifest = load_manifest()
    if command == "fetch":
        register_document(
            manifest,
            {
                "url": TSE_LIST_URL,
                "partido": None,
                "tipo": "lista_oficial_partidos",
                "data_do_documento": None,
                "baixado_em": None,
                "sha256": None,
                "arquivo": None,
                "status": "unavailable",
                "motivo": TSE_BLOCK_REASON,
            },
        )
        for party, kind, url in PARTY_SOURCES:
            fetch_source(manifest, party, kind, url)
    elif command == "ingest-manual":
        ingest_manual(manifest)
    elif command != "build":
        print(__doc__)
        return 2
    write_manual_checklist()
    save_manifest(manifest)
    build_all(manifest)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
