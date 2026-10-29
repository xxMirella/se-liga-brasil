"""Validate a whole dated official roster before it can become a Chamber snapshot."""

import hashlib
import json
from datetime import datetime
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

API_ROOT = "https://dadosabertos.camara.leg.br/api/v2/"


def read_snapshot_source(storage, evidence):
    url = evidence["url"]
    if not url.startswith(API_ROOT):
        raise ValueError("CHAMBER_SNAPSHOT_UNOFFICIAL_SOURCE")
    content = (storage / (evidence["sha256"] + ".json")).read_bytes()
    if hashlib.sha256(content).hexdigest() != evidence["sha256"]:
        raise ValueError("CHAMBER_SNAPSHOT_SOURCE_HASH_MISMATCH")
    return json.loads(content)


def load_dated_roster(storage, cutoff):
    manifest = json.loads((storage / "sources.json").read_text())
    pages = [row for row in manifest if urlparse(row["url"]).path == "/api/v2/deputados"]
    if not pages:
        raise ValueError("CHAMBER_SNAPSHOT_NO_ROSTER_PAGES")
    expected = API_ROOT + "deputados?itens=100"
    members, dates = [], set()
    for evidence in pages:
        if evidence["url"] != expected:
            raise ValueError("CHAMBER_SNAPSHOT_INCOMPLETE_PAGINATION")
        document = read_snapshot_source(storage, evidence)
        observed = datetime.fromisoformat(evidence["fetched_at"])
        if observed.tzinfo is None:
            raise ValueError("CHAMBER_SNAPSHOT_UNDATED_SOURCE")
        dates.add(observed.astimezone(ZoneInfo("America/Belem")).date())
        members.extend(document["dados"])
        expected = next((link["href"] for link in document.get("links", [])
                         if link["rel"] == "next"), None)
    if expected or len(dates) != 1 or max(dates) > cutoff:
        raise ValueError("CHAMBER_SNAPSHOT_INCOHERENT_OR_AFTER_CUTOFF")
    if len({str(row["id"]) for row in members}) != len(members):
        raise ValueError("CHAMBER_SNAPSHOT_DUPLICATE_DEPUTY")
    if len(members) > 513 or any(row["idLegislatura"] != 57 for row in members):
        raise ValueError("CHAMBER_SNAPSHOT_INVALID_INSTITUTIONAL_SCOPE")
    return members, pages, dates.pop()
