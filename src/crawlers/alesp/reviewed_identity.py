"""Collect official evidence for explicitly reviewed cross-source identifier mappings."""

import json
from pathlib import Path

from crawlers.alesp.identity import (
    PROFILE_BASE_URL,
    acquire_identity_resource,
    identity_resource,
    normalize_birthday,
)
from normalization.identity import normalize_person_name
from service.ingestion.contracts import DownloadBudget, IngestionError
from storage.files import hash_content, load_json

REVIEWED_IDENTITIES = Path(__file__).resolve().parents[3] / "config/alesp-reviewed-identities.json"


def validate_reviewed_profile(profile, case) -> None:
    if str(profile.get("idParlamentar")) != case["source_subject_id"]:
        raise IngestionError("REVIEWED_IDENTITY_SUBJECT_MISMATCH")
    if str(profile.get("nuMatricula")) != case["matricula"]:
        raise IngestionError("REVIEWED_IDENTITY_SUBJECT_MISMATCH")
    name = normalize_person_name(profile["txNomeParlamentar"])
    if name != normalize_person_name(case["target_public_name"]):
        raise IngestionError("REVIEWED_IDENTITY_PUBLIC_NAME_CHANGED")
    actual_birthday = normalize_birthday((profile.get("biografia") or {}).get("dtAniversario"))
    if actual_birthday != case.get("source_birthday"):
        raise IngestionError("REVIEWED_SOURCE_BIRTHDAY_CHANGED")
    codes = {
        str(row.get("partido", {}).get("nuLegenda", "")).zfill(2)
        for row in profile.get("listaFiliacoes", [])
    }
    if case["target_political_party_code"] not in codes:
        raise IngestionError("REVIEWED_IDENTITY_PARTY_EVIDENCE_CHANGED")


def plan_reviewed_resources(cases) -> dict:
    """Index evidence by URL so shared sources are acquired once."""
    resources = {}
    for case in cases:
        profile_url = PROFILE_BASE_URL + case["matricula"]
        resources[profile_url] = identity_resource(
            "profile-" + case["matricula"], profile_url, ".json"
        )
        for url in case["evidence_urls"]:
            if url not in resources:
                suffix = ".json" if "legis-api-portal-prd" in url else ".html"
                resources[url] = identity_resource("review-" + hash_content(url), url, suffix)
    return resources


def assemble_reviewed_identity(case, registry, acquired) -> dict:
    profile_url = PROFILE_BASE_URL + case["matricula"]
    payload, profile_source = acquired[profile_url]
    profile = json.loads(payload)
    validate_reviewed_profile(profile, case)
    evidence_urls = dict.fromkeys(case["evidence_urls"])
    sources = [profile_source]
    sources.extend(acquired[url][1] for url in evidence_urls if url != profile_url)
    return case | {
        "sources": sources,
        "affiliations": profile.get("listaFiliacoes", []),
        "reviewed_on": registry["reviewed_on"],
        "scope": registry["scope"],
    }


def collect_reviewed_identities(configuration, client) -> list:
    registry = load_json(REVIEWED_IDENTITIES)
    if registry["status"] != "reviewed_against_official_sources":
        raise IngestionError("IDENTITY_MAPPING_NOT_REVIEWED")
    if registry["birth_date_changes_allowed"]:
        raise IngestionError("IDENTITY_MAPPING_CANNOT_CHANGE_BIRTH_DATE")
    resources = plan_reviewed_resources(registry["exceptions"])
    budget = DownloadBudget()
    acquired = {
        url: acquire_identity_resource(resource, configuration, client, budget)
        for url, resource in resources.items()
    }
    return [assemble_reviewed_identity(case, registry, acquired) for case in registry["exceptions"]]
