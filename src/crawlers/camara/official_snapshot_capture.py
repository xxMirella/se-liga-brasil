"""Capture only official read-only Chamber resources with immutable content hashes."""

import hashlib
import json
from datetime import UTC, datetime

import httpx

from service.acquisition.http_client import validate_official_url
from storage.files import save_json

RESOURCES = (
    "https://dadosabertos.camara.leg.br/api/v2/deputados?itens=100",
    "https://dadosabertos.camara.leg.br/api/v2/partidos/36896",
    "https://dadosabertos.camara.leg.br/api/v2/legislaturas/57",
    *("https://www.camara.leg.br/SitCamaraWS/Deputados.asmx/ObterDetalhesDeputado"
      f"?ideCadastro={identifier}&numLegislatura=56" for identifier in (209189, 74574, 178874)),
)


def capture_chamber_snapshot(storage):
    storage.mkdir(parents=True, exist_ok=True)
    evidence = []
    with httpx.Client(timeout=60, follow_redirects=False) as client:
        for resource in RESOURCES:
            url = resource
            seen = set()
            while url:
                if url in seen or len(seen) >= 100:
                    raise ValueError("CHAMBER_SOURCE_PAGINATION_CYCLE_OR_LIMIT")
                seen.add(url)
                artifact, url = capture_chamber_page(client, storage, url)
                evidence.append(artifact)
    save_json(storage / "sources.json", evidence)
    return evidence


def capture_chamber_page(client, storage, url):
    validate_official_url(url, {"dadosabertos.camara.leg.br", "www.camara.leg.br"})
    response = client.get(url)
    response.raise_for_status()
    digest = hashlib.sha256(response.content).hexdigest()
    suffix = ".xml" if "Deputados.asmx" in url else ".json"
    destination = storage / (digest + suffix)
    if not destination.exists():
        destination.write_bytes(response.content)
    evidence = {"url": url, "sha256": digest, "suffix": suffix, "http_status": 200,
                "fetched_at": datetime.now(UTC).isoformat()}
    document = json.loads(response.content) if suffix == ".json" else {}
    next_url = next((row["href"] for row in document.get("links", [])
                     if row["rel"] == "next"), None)
    return evidence, next_url
