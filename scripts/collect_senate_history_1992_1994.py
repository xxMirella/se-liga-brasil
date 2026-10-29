"""Archive original Senate open-data responses for the 1992-1994 occupants.

Paced (about 1.5 requests/second), sequential, identifiable User-Agent, backoff
on 429/5xx. Original bytes are stored untouched; every response, including 404 and
empty ones, is recorded in manifest.json. Resumable: recorded entries are kept.
"""

import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

API_BASE = "https://legis.senado.leg.br/dadosabertos/"  # hardcode-ok: URL oficial da fonte e User-Agent identificável do coletor  # noqa: E501
USER_AGENT = "se-liga-brasil-research/1.0 (mirella.mih1006@gmail.com; paced open-data archive)"  # hardcode-ok: URL oficial da fonte e User-Agent identificável do coletor  # noqa: E501
MIN_INTERVAL_SECONDS = 0.7
MAX_ATTEMPTS = 5
TIMEOUT_SECONDS = 60
RETRYABLE = {429, 500, 502, 503, 504}
INVENTORY_PATH = Path("src/service/political_dashboard/senate_orientation_1992_1994.json")
RESEARCH_INVENTORY_PATH = Path("data/political-orientation/itamar-senate-inventory-1992-1994.json")
OUTPUT_DIRECTORY = Path("data/political-dashboard/senate-history-1992-1994-source")
PERSON_ENDPOINTS = {
    "detail": "senador/{id}.json",
    "mandates": "senador/{id}/mandatos.json",
    "affiliations": "senador/{id}/filiacoes.json",
    "leaves": "senador/{id}/licencas.json",
}
GLOBAL_ENDPOINTS = {
    "legislature-47": "senador/lista/legislatura/47.json",
    "legislature-48": "senador/lista/legislatura/48.json",
    "legislature-49": "senador/lista/legislatura/49.json",
    "legislature-48-49": "senador/lista/legislatura/48/49.json",
    "parties": "senador/partidos.json",
}


def occupant_ids() -> list[str]:
    inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    ids = {seat["occupant_source_id"] for snap in inventory["snapshots"] for seat in snap["seats"]}
    research = json.loads(RESEARCH_INVENTORY_PATH.read_text(encoding="utf-8"))
    ids |= {person["source_person_id"] for person in research["people"]}
    return sorted(ids, key=int)


def fetch(url: str) -> tuple[int, bytes]:
    for attempt in range(MAX_ATTEMPTS):
        request = urllib.request.Request(
            url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
        )
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as error:
            body = error.read()
            if error.code not in RETRYABLE:
                return error.code, body
            retry_after = error.headers.get("Retry-After", "")
            delay = int(retry_after) if retry_after.isdigit() else 2 ** (attempt + 1)
        except (urllib.error.URLError, TimeoutError):
            delay = 2 ** (attempt + 1)
        time.sleep(delay)
    return 0, b""


def archive_one(kind: str, endpoint: str, senator_id: str | None) -> dict:
    url = API_BASE + endpoint
    status, body = fetch(url)
    name = f"{senator_id}.json" if senator_id else f"{kind}.json"
    relative = Path("raw") / (kind if senator_id else "lists") / name
    target = OUTPUT_DIRECTORY / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(body)
    return {
        "url": url,
        "endpoint": endpoint,
        "kind": kind,
        "senator_id": senator_id,
        "http_status": status,
        "baixado_em": datetime.now(UTC).isoformat(timespec="seconds"),
        "sha256": hashlib.sha256(body).hexdigest(),
        "bytes": len(body),
        "path": str(relative),
    }


def planned_requests(ids: list[str]) -> list[tuple[str, str, str | None]]:
    plan = [(kind, endpoint, None) for kind, endpoint in GLOBAL_ENDPOINTS.items()]
    for senator_id in ids:
        for kind, template in PERSON_ENDPOINTS.items():
            plan.append((kind, template.format(id=senator_id), senator_id))
    return plan


def load_manifest() -> list[dict]:
    path = OUTPUT_DIRECTORY / "manifest.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def save_manifest(entries: list[dict]) -> None:
    (OUTPUT_DIRECTORY / "manifest.json").write_text(
        json.dumps(entries, ensure_ascii=False, indent=1), encoding="utf-8"
    )


def main() -> None:
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    entries = load_manifest()
    done = {entry["endpoint"] for entry in entries if entry["http_status"] in (200, 404)}
    for kind, endpoint, senator_id in planned_requests(occupant_ids()):
        if endpoint in done:
            continue
        entries = [entry for entry in entries if entry["endpoint"] != endpoint]
        entries.append(archive_one(kind, endpoint, senator_id))
        save_manifest(entries)
        time.sleep(MIN_INTERVAL_SECONDS)
    statuses = sorted({entry["http_status"] for entry in entries})
    print(f"{len(entries)} responses archived; statuses {statuses}", file=sys.stderr)


if __name__ == "__main__":
    main()
