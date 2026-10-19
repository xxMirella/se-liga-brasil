"""Recover official photos from trusted normalized profiles and immutable local raw."""

import hashlib
import json
from collections import Counter
from pathlib import Path

from normalization.identity import normalize_person_name
from normalization.official_media import normalize_official_media_url

HOSTS = {
    "camara": {"www.camara.leg.br", "camara.leg.br", "www.camara.gov.br"},
    "senado": {"www.senado.leg.br", "senado.leg.br"},
}


def load_local_senate_photos(directory, source_urls):
    profiles = {}
    root = Path(directory).resolve()
    for manifest_path in (root / "manifests").glob("senado-*.json"):
        try:
            manifest = json.loads(manifest_path.read_text())
            if manifest["source_url"] not in source_urls:
                continue
            path = Path(manifest["path"]).resolve()
            if not path.is_relative_to(root) or path.stat().st_size > 20 * 1024**2:
                continue
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != manifest["sha256"]:
                continue
            profile = json.loads(raw)["DetalheParlamentar"]["Parlamentar"]
            profiles[manifest["source_url"]] = profile
        except (KeyError, TypeError, ValueError, OSError):
            continue
    return profiles


def resolve_profile_photo(row, senate_profiles):
    profile = row["profile"]
    value = profile.get("photoUrl")
    if not value and row["source_code"] == "senado":
        raw = senate_profiles.get(row["source_url"], {})
        identification = raw.get("IdentificacaoParlamentar", {})
        name = identification.get("NomeCompletoParlamentar")
        birth = raw.get("DadosBasicosParlamentar", {}).get("DataNascimento")
        if (
            not name
            or not profile.get("civilName")
            or not birth
            or birth != profile.get("birthDate")
        ):
            return None
        if normalize_person_name(name) != normalize_person_name(profile.get("civilName")):
            return None
        value = identification.get("UrlFotoParlamentar")
    return normalize_official_media_url(value, HOSTS[row["source_code"]], upgrade_http=True)


def summarize_profiles(rows):
    sources = {}
    for source in HOSTS:
        selected = [row for row in rows if row["source_code"] == source]
        available = sum(
            bool(normalize_official_media_url(row["photo_url"], set().union(*HOSTS.values())))
            for row in selected
        )
        sources[source] = {"linked_people": len(selected), "https_official_photos": available}
    return sources


def backfill_profile_photos(repository, directory, *, limit=10000, apply=False):
    if not 1 <= limit <= 10000:
        raise ValueError("INVALID_PROFILE_LIMIT")
    rows = repository.fetch_linked_profiles(limit)
    truncated = len(rows) > limit
    rows = rows[:limit]
    raw = load_local_senate_photos(directory, {row["source_url"] for row in rows})
    proposals = {}
    missing = Counter()
    for row in rows:
        source = row["source_code"]
        current = normalize_official_media_url(row["photo_url"], set().union(*HOSTS.values()))
        url = resolve_profile_photo(row, raw)
        if current:
            continue
        if not url:
            missing[source] += 1
            continue
        proposals.setdefault(
            row["person_id"], {**row, "photo_url": url, "previous_photo_url": row["photo_url"]}
        )
    updated = (
        repository.save_official_photos(list(proposals.values())) if apply and proposals else 0
    )
    return {
        "before": summarize_profiles(rows),
        "profile_rows_truncated": truncated,
        "proposed_people": len(proposals),
        "updated_people": updated,
        "missing_valid_photo_evidence": dict(missing),
        "applied": apply,
    }
