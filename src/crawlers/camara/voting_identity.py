"""Transient provider keys bridge verified full names and dates to internal UUIDs."""

import json
import re
from datetime import date
from urllib.parse import urlsplit

from crawlers.camara.configuration import API_BASE, OFFICIAL_HOSTS
from database.personal_evidence import (
    lookup_unique_people_by_document,
    lookup_unique_people_by_name_birth,
)
from normalization.identity import normalize_person_name
from normalization.scalars import normalize_digits
from service.acquisition.downloader import build_downloaded_artifact, is_cached_archive_intact
from service.acquisition.http_client import validate_official_url
from service.identity_resolution.evidence import IdentityEvidenceBuilder, load_identity_key
from service.ingestion.contracts import IngestionError, Resource
from storage.files import hash_content, hash_file, load_json


def voter_profile_key(vote):
    deputy = vote.get("deputado_")
    if not isinstance(deputy, dict):
        return None
    return normalize_digits(deputy.get("id"), required=False)


def requested_profile_keys(events):
    keys = set()
    for event in events:
        for vote in event["votes"]:
            if not isinstance(vote, dict):
                raise IngestionError("CAMARA_PERSON_VOTE_SCHEMA_CHANGED")
            key = voter_profile_key(vote)
            if key is not None:
                keys.add(key)
    return keys


def cached_profile_artifact(configuration, key):
    url = API_BASE + "deputados/" + key
    resource_id = "camara-" + hash_content(url)
    manifest = load_json(configuration.storage_directory / "manifests" / (resource_id + ".json"))
    if manifest is None:
        return None
    year = date.fromisoformat(manifest["fetched_at"][:10]).year
    resource = Resource(resource_id, "profile", url, "profile", year, "camara", file_suffix=".json")
    if not is_cached_archive_intact(manifest, resource):
        return None
    return build_downloaded_artifact(resource, manifest, "cached")


def profile_evidence(artifact):
    validate_official_url(artifact.resource.url, OFFICIAL_HOSTS)
    path = urlsplit(artifact.resource.url).path
    match = re.fullmatch(r"/api/v2/deputados/([1-9][0-9]*)", path)
    if not match or urlsplit(artifact.resource.url).hostname != "dadosabertos.camara.leg.br":
        raise IngestionError("UNTRUSTED_CAMARA_IDENTITY_PROFILE")
    if hash_file(artifact.path) != artifact.sha256:
        raise IngestionError("CAMARA_IDENTITY_ARTIFACT_CHANGED")
    profile = json.loads(artifact.path.read_bytes()).get("dados")
    if not isinstance(profile, dict) or str(profile.get("id")) != match[1]:
        raise IngestionError("CAMARA_IDENTITY_PROFILE_KEY_MISMATCH")
    if not profile.get("nomeCivil") or not profile.get("dataNascimento"):
        return None
    return {
        "transient_key": match[1],
        "document_fingerprint": profile_document_fingerprint(profile),
        "normalized_name": normalize_person_name(profile["nomeCivil"]),
        "birth_date": date.fromisoformat(profile["dataNascimento"]).isoformat(),
        "artifact": artifact,
    }


def collect_identity_profiles(acquisition, events, configuration, supplied=()):
    requested = requested_profile_keys(events)
    artifacts, attempts, deferred = {}, 0, 0
    for artifact in supplied:
        evidence = profile_evidence(artifact)
        if evidence and evidence["transient_key"] in requested:
            artifacts[evidence["transient_key"]] = artifact
    for key in sorted(requested - artifacts.keys(), key=int):
        artifact = cached_profile_artifact(configuration, key)
        if artifact is None:
            if attempts >= configuration.max_identity_profiles:
                deferred += 1
                continue
            _, artifact = acquisition.json_document("deputados/" + key, "camara_profile")
            attempts += 1
        artifacts[key] = artifact
    return artifacts, {
        "identity_profile_requests": attempts,
        "identity_profiles_deferred": deferred,
    }


def resolve_voting_people(connection, artifacts):
    evidence = []
    for artifact in artifacts.values():
        item = profile_evidence(artifact)
        if item:
            evidence.append(item)
    documents = lookup_unique_people_by_document(connection, evidence)
    matches = lookup_unique_people_by_name_birth(
        connection, [item for item in evidence if not item.get("document_fingerprint")]
    )
    index = {}
    for item in evidence:
        fingerprint = item.get("document_fingerprint")
        person_id = (
            documents.get(fingerprint)
            if fingerprint
            else matches.get((item["normalized_name"], item["birth_date"]))
        )
        if person_id:
            index[item["transient_key"]] = {"person_id": person_id, "artifact": item["artifact"]}
    return index


def profile_document_fingerprint(profile):
    from normalization.identity import normalize_cpf

    try:
        document = normalize_cpf(profile.get("cpf"))
    except IngestionError:
        return None
    if document is None:
        return None
    return IdentityEvidenceBuilder(load_identity_key()).build_evidence(
        profile["nomeCivil"], cpf=document
    )["documentFingerprint"]
