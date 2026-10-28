"""Read the dated political roster, excluding the separately printed licensed column."""

import re
import subprocess
import unicodedata
from datetime import date

from service.ingestion.contracts import IngestionError

MEMBER = re.compile(r"\d{2}\.\s+Deputad[oa]\s+(.+?)\s*\(([^)\n]+)\)*\s*$")


def extract_diary_text(path):
    result = subprocess.run(
        ["pdftotext", "-layout", str(path), "-"], capture_output=True, timeout=30, check=False
    )
    if result.returncode:
        raise IngestionError("ALEMA_DIARY_PDF_EXTRACTION_FAILED")
    return result.stdout.decode("utf-8")


def match_diary_source_ids(members, legislative_registry):
    """Link within the same official source; never resolve canonical people by name."""
    registry = {}
    for row in legislative_registry:
        for label in [row["parliamentaryName"], row["fullName"]]:
            registry.setdefault(comparison_name(label), set()).add(row["id"])
    registry[comparison_name("Janaína")] = registry[comparison_name("Janaina Lima")]
    result = []
    for member in members:
        ids = registry.get(comparison_name(member["name"]), set())
        if len(ids) != 1:
            raise IngestionError("ALEMA_DIARY_REGISTRY_NAME_AMBIGUOUS_OR_MISSING")
        result.append({**member, "provider_subject_id": f"alemalegis:{next(iter(ids))}"})
    return result


def comparison_name(value):
    normalized = unicodedata.normalize("NFKD", value.lower())
    return re.sub("[^a-z]", "", "".join(c for c in normalized if not unicodedata.combining(c)))


def parse_diary_roster(text, publication_date):
    first_page = text.split("\f", 1)[0]
    expected_date = f"{publication_date.day:02} DE OUTUBRO DE {publication_date.year}"
    if publication_date.month != 10 or expected_date not in first_page:
        raise IngestionError("ALEMA_DIARY_PUBLICATION_DATE_MISMATCH")
    if "20.ª LEGISLATURA" not in first_page:
        raise IngestionError("ALEMA_DIARY_LEGISLATURE_MISSING")
    section = first_page.split("BLOCO PARLAMENTAR UNIDOS PELO MARANHÃO", 1)
    if len(section) != 2:
        raise IngestionError("ALEMA_DIARY_POLITICAL_ROSTER_MISSING")
    members, licensed = read_roster_columns(section[1])
    if len(members) != 42 or len(licensed) != 2:
        raise IngestionError("ALEMA_DIARY_ROSTER_SIZE_UNEXPECTED")
    if len({row["name"] for row in members}) != 42:
        raise IngestionError("ALEMA_DIARY_DUPLICATE_MEMBER")
    return {"observed_on": publication_date.isoformat(), "members": members, "licensed": licensed}


def read_roster_columns(section):
    members, licensed = [], []
    licensed_section = False
    for line in section.splitlines():
        if "LIDERANÇA DO GOVERNO" in line:
            break
        if "LICENCIADOS" in line:
            licensed_section = True
            continue
        columns = re.split(r"\s{4,}(?=\d{2}\.)", line.strip())
        if licensed_section:
            read_licensed_and_psd_columns(line, columns, licensed, members)
        else:
            for column in columns:
                append_member(column, members)
    return members, licensed


def read_licensed_and_psd_columns(line, columns, licensed, members):
    if re.match(r"\s{50,}\d{2}\.", line):
        append_member(line, members)
        return
    append_member(columns[0], licensed)
    for column in columns[1:]:
        append_member(column, members)


def append_member(column, members):
    match = MEMBER.search(column.strip())
    if match:
        name, political_party = match.groups()
        members.append(
            {"name": name.strip(), "political_party": political_party.strip().rstrip(")")}
        )


def october_publication_date(value):
    """Keep the initial verified layout explicitly scoped to the reviewed October editions."""
    parsed = date.fromisoformat(value)
    if parsed.year != 2026 or parsed.month != 10:
        raise ValueError("ALEMA_DIARY_LAYOUT_NOT_REVIEWED_FOR_DATE")
    return parsed
