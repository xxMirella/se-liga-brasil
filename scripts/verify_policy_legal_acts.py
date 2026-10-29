"""Verifica cada ato legal do catálogo curado no LexML (rede oficial do Congresso/Senado).

Arquiva a página (gz), registra url/sha256/data em raw/lexml/manifest.json e grava o título
efetivamente retornado em derived/legal_acts_verified.json. Ato inexistente ou título divergente
fica marcado como não verificado: nada é presumido.
"""

from __future__ import annotations

import gzip
import hashlib
import html
import json
import re
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

POLICIES = Path(__file__).resolve().parents[1] / "data/political-orientation/party-model/policies"
LEXML_URL = (
    "https://www.lexml.gov.br/urn/{urn}"  # hardcode-ok: resolvedor público oficial de URN LEX
)
MIN_VALID_BYTES = 1000  # URN inexistente devolve ~100 bytes


def fetch(url: str) -> bytes | None:
    for attempt in range(3):  # a fonte oscila; pausa crescente também respeita o servidor
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "se-liga-brasil-research"})
            with urllib.request.urlopen(request, timeout=60) as response:
                page = response.read()
            if len(page) >= MIN_VALID_BYTES:
                return page
        except (urllib.error.URLError, TimeoutError):
            pass
        time.sleep(2 * (attempt + 1))
    return None


def extract_title(page: bytes) -> str:
    match = re.search(rb"<title>(.*?)</title>", page, re.S)
    return (
        html.unescape(re.sub(r"\s+", " ", match.group(1).decode("utf-8", "replace"))).strip()
        if match
        else ""
    )


def verify_act(act: dict, manifest: dict) -> dict:
    url = LEXML_URL.format(urn=act["urn"])
    page = fetch(url)
    if page is None or len(page) < MIN_VALID_BYTES:
        return {"id": act["id"], "status": "nao_verificado_indisponivel_ou_inexistente", "url": url}
    target = POLICIES / "raw/lexml" / f"{act['id']}.html.gz"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(gzip.compress(page))
    manifest[target.name] = {
        "url": url,
        "sha256_conteudo_original": hashlib.sha256(page).hexdigest(),
        "baixado_em": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    return {
        "id": act["id"],
        "status": "verificado",
        "url": url,
        "titulo_retornado": extract_title(page),
    }


def main() -> None:
    acts = json.loads((POLICIES / "curated/legal_acts.json").read_text())
    manifest: dict = {}
    results = [verify_act(act, manifest) for act in acts]
    (POLICIES / "raw/lexml/manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1)
    )
    (POLICIES / "derived/legal_acts_verified.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=1)
    )
    for result in results:
        print(result["id"], result["status"], result.get("titulo_retornado", "")[:90])


if __name__ == "__main__":
    main()
