"""Reconcile official monthly attendance with individually published deputy profiles."""

import html
import json
import re

from service.ingestion.contracts import IngestionError


def parse_attendance(payload):
    document = payload.decode() if isinstance(payload, bytes) else payload
    rows = [json.loads(html.unescape(item)) for item in re.findall(
        r"data-item='([^']+)'", document
    )]
    identifiers = [str(row["codProponente"]) for row in rows]
    if len(rows) != 55 or len(set(identifiers)) != 55:
        raise IngestionError("ALRS_ATTENDANCE_EXPECTED_55_UNIQUE_MEMBERS")
    if any(int(row.get("presenca", 0)) <= 0 for row in rows):
        raise IngestionError("ALRS_ATTENDANCE_REQUIRES_DOCUMENTED_PRESENCE")
    if len({(row["ano"], row["mesNumerico"]) for row in rows}) != 1:
        raise IngestionError("ALRS_ATTENDANCE_MIXED_PERIODS")
    return rows


def parse_profile(payload):
    document = payload.decode() if isinstance(payload, bytes) else payload
    name = re.search(r'<h2[^>]*class="title deputado-name"[^>]*>(.*?)</h2>', document, re.S)
    affiliation = re.search(r"Partido:\s*<strong>([^<]+)</strong>", document)
    if not name or not affiliation:
        raise IngestionError("ALRS_PROFILE_SCHEMA_CHANGED")
    return {
        "name": html.unescape(name.group(1)).removeprefix("Dep. ").strip(),
        "political_party": html.unescape(affiliation.group(1)).strip(),
    }


def parse_current_roster(payload):
    document = json.loads(payload)
    attendance = parse_attendance(document["attendance_html"])
    profiles = document["profiles"]
    members = []
    for row in attendance:
        identifier = str(row["codProponente"])
        profile = parse_profile(profiles[identifier])
        if profile["name"].strip().casefold() != row["nomeProponente"].strip().casefold():
            raise IngestionError("ALRS_ATTENDANCE_PROFILE_IDENTITY_MISMATCH")
        members.append({"provider_subject_id": identifier, **profile})
    return members
