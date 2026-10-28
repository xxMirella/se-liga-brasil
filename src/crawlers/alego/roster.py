"""Reconcile the official directory with dated absence and titular-return records."""

import re
from datetime import date
from html import unescape
from urllib.parse import urljoin

from parsing.html import decode_html
from service.ingestion.contracts import IngestionError

BASE_URL = "https://portal.al.go.leg.br"
DECEASED_ID = "138"
RETURNED_SUBSTITUTE_ID = "831"


def plain_text(payload):
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", decode_html(payload)))).strip()


def parse_directory(payload):
    source = decode_html(payload)
    tables = re.findall(r"<tbody>(.*?)</tbody>", source, re.S)
    if len(tables) != 1:
        raise IngestionError("ALEGO_DIRECTORY_TABLE_MISSING_OR_AMBIGUOUS")
    members = []
    for row in re.findall(r"<tr\b[^>]*>(.*?)</tr>", tables[0], re.S):
        identity = re.search(r"href=[\"']?(/deputados/perfil/(\d+))[\"']?>([^<]+)</a>", row)
        political_party = re.search(r'data-title="Partido">[^<]*\(([^)]+)\)</td>', row)
        if identity is None or political_party is None:
            raise IngestionError("ALEGO_DIRECTORY_IDENTITY_OR_PARTY_MISSING")
        path, identifier, name = identity.groups()
        members.append(
            {
                "provider_subject_id": identifier,
                "name": unescape(name).strip(),
                "political_party": political_party.group(1),
                "official_url": urljoin(BASE_URL, path),
            }
        )
    identifiers = {row["provider_subject_id"] for row in members}
    if len(members) != 43 or len(identifiers) != len(members):
        raise IngestionError("ALEGO_REVIEWED_DIRECTORY_SIZE_OR_UNIQUENESS_CHANGED")
    return members


def parse_absence_records(payload):
    records = []
    source = decode_html(payload)
    for row in re.findall(r"<tr\b[^>]*>(.*?)</tr>", source, re.S):
        identity = re.search(r"/deputados/perfil/(\d+)[\"']?>([^<]+)</a>", row)
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
        if identity is None or len(cells) != 4:
            continue
        values = [plain_text(re.sub(r"<b\b.*?</b>", "", c, flags=re.S).encode()) for c in cells]
        records.append(
            {
                "provider_subject_id": identity.group(1),
                "name": unescape(identity.group(2)),
                "reason": values[1],
                "starts_on": values[2],
                "ends_on": values[3],
            }
        )
    if not records:
        raise IngestionError("ALEGO_ABSENCE_RECORDS_MISSING")
    return records


def validate_return_notice(payload):
    text = plain_text(payload)
    required = [
        "07 de Outubro de 2026",
        "Coronel Adailton e Julio Pina",
        "retomada de seus mandatos",
        "Eliel Júnior e Givago Valadares retornam",
        "Thiago Albernaz",
        "Amilton Filho",
    ]
    if not all(value in text for value in required):
        raise IngestionError("ALEGO_DATED_TITULAR_RETURN_PROOF_MISSING")


def reconcile_current_roster(directory, absences, return_notice, observed_on):
    if observed_on.year != 2026 or observed_on < date(2026, 10, 7):
        raise IngestionError("ALEGO_RECONCILIATION_PREDATES_RETURN_PROOF")
    validate_return_notice(return_notice)
    members = parse_directory(directory)
    records = parse_absence_records(absences)
    excluded = verified_exclusions(records)
    active = [row for row in members if row["provider_subject_id"] not in excluded]
    active_ids = {row["provider_subject_id"] for row in active}
    if len(active) != 41 or not {"142", "145", "149"}.issubset(active_ids):
        raise IngestionError("ALEGO_RECONCILED_ROSTER_CAPACITY_OR_TITULAR_MISMATCH")
    return active, [row for row in members if row["provider_subject_id"] in excluded]


def verified_exclusions(records):
    required = {
        (DECEASED_ID, "Falecimento", "26/09/2026"),
        (RETURNED_SUBSTITUTE_ID, "Retorno do Titular", "07/10/2026"),
    }
    documented = {(r["provider_subject_id"], r["reason"], r["starts_on"]) for r in records}
    if not required.issubset(documented):
        raise IngestionError("ALEGO_DOCUMENTED_EXCLUSION_MISSING")
    return {DECEASED_ID, RETURNED_SUBSTITUTE_ID}
