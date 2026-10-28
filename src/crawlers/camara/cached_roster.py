"""Replay the complete official current roster without making an HTTP request."""

import json
from datetime import datetime
from zoneinfo import ZoneInfo

from crawlers.camara.configuration import API_BASE, OFFICIAL_HOSTS
from service.acquisition.downloader import build_downloaded_artifact, is_cached_archive_intact
from service.acquisition.http_client import validate_official_url
from service.ingestion.contracts import IngestionError, Resource
from storage.files import hash_content, load_json


def load_cached_current_roster(storage):
    url = API_BASE + "deputados?itens=100"
    members, artifacts, seen = [], [], set()
    for _ in range(100):
        validate_official_url(url, OFFICIAL_HOSTS)
        if url in seen:
            raise IngestionError("CAMARA_PAGINATION_CYCLE")
        seen.add(url)
        resource_id = "camara-" + hash_content(url)
        manifest = load_json(storage / "manifests" / (resource_id + ".json"))
        if manifest is None:
            return [], []
        resource = Resource(
            resource_id,
            "camara_roster",
            url,
            "camara_roster",
            int(manifest["fetched_at"][:4]),
            "camara-enrichment",
            file_suffix=".json",
        )
        if not is_cached_archive_intact(manifest, resource):
            raise IngestionError("CAMARA_ROSTER_ARCHIVE_INTEGRITY_FAILED")
        artifact = build_downloaded_artifact(resource, manifest, "cached")
        document = json.loads(artifact.path.read_bytes())
        members.extend(document["dados"])
        artifacts.append(artifact)
        url = next(
            (link["href"] for link in document.get("links", []) if link["rel"] == "next"), None
        )
        if url is None:
            return members, artifacts
    raise IngestionError("CAMARA_PAGE_LIMIT_EXCEEDED")


def coherent_roster_observed_on(artifacts):
    dates = {
        datetime.fromisoformat(artifact.fetched_at).astimezone(ZoneInfo("America/Belem")).date()
        for artifact in artifacts
    }
    return dates.pop() if len(dates) == 1 else None
