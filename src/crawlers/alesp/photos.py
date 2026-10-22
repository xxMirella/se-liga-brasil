"""Institutional photo links from verified, immutable ALESP profile evidence."""

from pathlib import Path

from crawlers.alesp.institutional_records import institutional_profiles
from normalization.official_media import normalize_official_media_url
from service.ingestion.contracts import IngestionError
from storage.files import load_json

PHOTO_HOSTS = frozenset({"www3.al.sp.gov.br", "www.al.sp.gov.br"})


def normalize_profile_photo(value):
    if isinstance(value, str) and value.startswith("/biografia/fotos/"):
        value = "https://www3.al.sp.gov.br/legis" + value
    return normalize_official_media_url(value, PHOTO_HOSTS)


def profiles_with_cached_photos(resolutions):
    """Called only after the evidence checksums have been verified."""
    for resolution in resolutions:
        if resolution.get("status") != "matched":
            yield resolution
            continue
        subjects = []
        for subject in resolution.get("official_subjects", []):
            photo = cached_subject_photo(subject)
            subjects.append(subject | {"photo_url": normalize_profile_photo(photo)})
        yield resolution | {"official_subjects": subjects}


def cached_photo_records(resolutions, person_ids):
    for resolution in profiles_with_cached_photos(resolutions):
        for subject in resolution.get("official_subjects", []):
            if not subject.get("photo_url"):
                continue
            single = resolution | {"official_subjects": [subject]}
            for profile in institutional_profiles([single], person_ids):
                yield {
                    "personId": profile["personId"],
                    "photoUrl": subject["photo_url"],
                    "observedAt": profile["observedAt"],
                    "evidence": profile["evidence"],
                }


def cached_subject_photo(subject):
    for source in subject.get("sources", []):
        if source.get("evidence_kind") != "profile" or not source.get("path"):
            continue
        profile = load_json(Path(source["path"]), {})
        if str(profile.get("idParlamentar")) != str(subject.get("source_subject_id")) or str(
            profile.get("nuMatricula")
        ) != str(subject.get("matricula")):
            raise IngestionError("ALESP_PHOTO_PROFILE_SUBJECT_MISMATCH")
        biography = profile.get("biografia") or {}
        if not isinstance(biography, dict):
            raise IngestionError("ALESP_IDENTITY_PROFILE_SCHEMA_CHANGED")
        return normalize_profile_photo(biography.get("txFotoGrande"))
    return normalize_profile_photo(subject.get("photo_url"))
