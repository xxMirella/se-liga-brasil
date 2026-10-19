"""Resolve cached institutional profiles in one query; provider keys stay transient."""

import json
import re
from datetime import date
from urllib.parse import urlsplit

from psycopg.types.json import Jsonb

from crawlers.senado.configuration import OFFICIAL_HOSTS
from normalization.identity import normalize_person_name
from service.acquisition.http_client import validate_official_url
from service.ingestion.contracts import DownloadedArtifact, IngestionError, Resource
from storage.files import hash_file, load_json


def cached_identity_profiles(storage, maximum=100):
    profiles = []
    for path in (storage / "manifests").glob("*.json"):
        manifest = load_json(path)
        url = manifest.get("source_url", "")
        parsed = urlsplit(url)
        if parsed.hostname != "legis.senado.leg.br" or not re.fullmatch(
            r"/dadosabertos/senador/[0-9]+\.json", parsed.path
        ):
            continue
        if len(profiles) >= maximum:
            raise IngestionError("SENATE_IDENTITY_PROFILE_LIMIT_EXCEEDED")
        year = date.fromisoformat(manifest["fetched_at"][:10]).year
        resource = Resource(
            path.stem, "profile", url, "profile", year, "senado", file_suffix=".json"
        )
        profiles.append(
            DownloadedArtifact(
                resource,
                path.parent.parent / "archives" / (manifest["sha256"] + ".json"),
                manifest["sha256"],
                manifest["fetched_at"],
                manifest["bytes"],
                "cached",
            )
        )
    return profiles


def profile_subject(artifact):
    validate_official_url(artifact.resource.url, OFFICIAL_HOSTS)
    if hash_file(artifact.path) != artifact.sha256:
        raise IngestionError("SENATE_IDENTITY_ARTIFACT_CHANGED")
    document = json.loads(artifact.path.read_bytes())
    profile = document.get("DetalheParlamentar", {}).get("Parlamentar", {})
    identification = profile.get("IdentificacaoParlamentar", {})
    birth = profile.get("DadosBasicosParlamentar", {}).get("DataNascimento")
    name = identification.get("NomeCompletoParlamentar")
    key = identification.get("CodigoParlamentar")
    if not key or not name or not birth:
        return None
    if urlsplit(artifact.resource.url).path != f"/dadosabertos/senador/{key}.json":
        raise IngestionError("SENATE_IDENTITY_PROFILE_KEY_MISMATCH")
    return {
        "key": str(key),
        "name": normalize_person_name(name),
        "birth_date": date.fromisoformat(birth).isoformat(),
        "sha256": artifact.sha256,
    }


def resolve_profile_identities(connection, artifacts):
    subjects = [subject for artifact in artifacts if (subject := profile_subject(artifact))]
    if not subjects:
        return {}
    rows = connection.execute(
        """SELECT DISTINCT p.id::text AS person_id,p.normalized_name,p.birth_date
        FROM se_liga_brasil.person p
        JOIN jsonb_to_recordset(%s) q(name text,birth_date date)
          ON p.normalized_name=q.name AND p.birth_date=q.birth_date
        WHERE NOT EXISTS(SELECT 1 FROM se_liga_brasil.person_identity_alias a
          WHERE a.alias_person_id=p.id)""",
        (Jsonb([{"name": x["name"], "birth_date": x["birth_date"]} for x in subjects]),),
    ).fetchall()
    identities = {}
    for row in rows:
        key = row["normalized_name"], row["birth_date"].isoformat()
        identities.setdefault(key, set()).add(row["person_id"])
    resolved = {}
    for subject in subjects:
        people = identities.get((subject["name"], subject["birth_date"]), set())
        if len(people) == 1:
            match = next(iter(people)), subject["sha256"]
            previous = resolved.setdefault(subject["key"], match)
            if previous[0] != match[0]:
                raise IngestionError("SENATE_IDENTITY_PROFILE_CONFLICT")
    return resolved
