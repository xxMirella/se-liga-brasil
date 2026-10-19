"""Bounded, cached profile acquisition for evidence missing from nominal voting."""

from dataclasses import dataclass, field
from urllib.parse import urlsplit

from crawlers.senado.voting_identity import profile_subject, resolve_profile_identities
from service.acquisition.downloader import is_recently_checked
from service.ingestion.contracts import IngestionError
from storage.files import load_json


def validate_identity_profile_budget(maximum):
    if isinstance(maximum, bool) or not isinstance(maximum, int) or not 0 <= maximum <= 100:
        raise IngestionError("INVALID_SENATE_IDENTITY_PROFILE_BUDGET")


def requested_voter_profile_keys(rows):
    """A provider key exists only in memory and in the immutable source artifact."""
    keys = set()
    for row in rows:
        if row["votacaoSecreta"] == "S":
            continue
        for vote in row.get("votos", []):
            key = str(vote.get("codigoParlamentar", ""))
            if key.isascii() and key.isdigit() and int(key) > 0:
                keys.add(key)
    return keys


@dataclass
class IdentityProfileAcquisition:
    maximum: int = 0
    attempted_keys: set[str] = field(default_factory=set)
    attempted: int = 0
    acquired: int = 0
    incomplete: int = 0
    deferred_keys: set[str] = field(default_factory=set)

    def mark_cached_profiles(self, artifacts, configuration=None):
        for artifact in artifacts:
            if configuration is not None and not recently_checked_profile(artifact, configuration):
                continue
            key = urlsplit(artifact.resource.url).path.rsplit("/", 1)[-1].removesuffix(".json")
            self.attempted_keys.add(key)

    def acquire_missing_profiles(self, acquisition, rows, resolved_index):
        keys = requested_voter_profile_keys(rows) - self.attempted_keys - resolved_index.keys()
        remaining = self.maximum - self.attempted
        selected = sorted(keys, key=int)[:remaining]
        self.deferred_keys.update(keys - set(selected))
        self.deferred_keys.difference_update(selected)
        artifacts = []
        for key in selected:
            self.attempted_keys.add(key)
            self.attempted += 1
            _, artifact = acquisition.json_document(f"senador/{key}.json", "senado_profile")
            subject = profile_subject(artifact)
            if subject is None:
                self.incomplete += 1
                continue
            if subject["key"] != key:
                raise IngestionError("SENATE_IDENTITY_PROFILE_KEY_MISMATCH")
            self.acquired += 1
            artifacts.append(artifact)
        return artifacts

    def extend_resolved_index(self, connection, acquisition, rows, resolved_index):
        artifacts = self.acquire_missing_profiles(acquisition, rows, resolved_index)
        if artifacts:
            resolved_index.update(resolve_profile_identities(connection, artifacts))

    def summary(self):
        return {
            "profile_acquisition_budget": self.maximum,
            "profile_acquisition_attempts": self.attempted,
            "profiles_with_personal_evidence": self.acquired,
            "profiles_without_personal_evidence": self.incomplete,
            "profile_acquisition_deferred": len(self.deferred_keys),
        }


def recently_checked_profile(artifact, configuration):
    path = configuration.storage_directory / "manifests" / (artifact.resource.resource_id + ".json")
    manifest = load_json(path, {"last_full_check_at": artifact.fetched_at})
    return is_recently_checked(manifest, configuration)
