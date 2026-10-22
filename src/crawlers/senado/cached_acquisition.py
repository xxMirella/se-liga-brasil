"""Explicit offline replay validates immutable archives and never opens an HTTP client."""

import json

from crawlers.senado.acquisition import json_resource
from crawlers.senado.configuration import OFFICIAL_HOSTS
from service.acquisition.downloader import build_downloaded_artifact, is_cached_archive_intact
from service.acquisition.http_client import validate_official_url
from service.ingestion.contracts import IngestionError
from storage.files import load_json


class CachedSenateAcquisition:
    def __init__(self, configuration):
        self.configuration = configuration

    def json_document(self, path, kind, *, resource_year=None):
        resource = json_resource(path, kind, resource_year)
        validate_official_url(resource.url, OFFICIAL_HOSTS)
        manifest = load_json(
            self.configuration.storage_directory / "manifests" / f"{resource.resource_id}.json"
        )
        if not is_cached_archive_intact(manifest, resource):
            raise IngestionError("SENATE_OFFLINE_ARCHIVE_MISSING_OR_CHANGED")
        artifact = build_downloaded_artifact(resource, manifest, "cached")
        return json.loads(artifact.path.read_bytes()), artifact
