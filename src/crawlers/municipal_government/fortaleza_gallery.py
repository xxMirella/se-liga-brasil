"""Official municipal annual chronology without invented day-level term boundaries."""

import re

from crawlers.state_government.parsing import evidence, visible_text
from storage.files import hash_content

ANNUAL_PERIOD = re.compile(r"^(\d{4})(?:\s*[-–]\s*(\d{4}|Hoje))?$")


def parse_fortaleza_government_gallery(artifact, observed_on):
    text = visible_text(artifact.path.read_bytes())
    if "Prefeitura Municipal de Fortaleza" not in text:
        raise ValueError("FORTALEZA_OFFICIAL_GALLERY_NOT_FOUND")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    records = []
    for index, line in enumerate(lines[:-1]):
        match = ANNUAL_PERIOD.fullmatch(line)
        if not match:
            continue
        start = int(match[1])
        end = observed_on.year if match[2] == "Hoje" else int(match[2] or match[1])
        if end < 1889:
            continue
        if start > end or end > observed_on.year:
            raise ValueError("FORTALEZA_GALLERY_INVALID_YEAR_INTERVAL")
        name = lines[index + 1]
        if ANNUAL_PERIOD.fullmatch(name):
            raise ValueError("FORTALEZA_GALLERY_MISSING_NAME")
        records.append(fortaleza_annual_exercise(artifact, name, start, end, line))
    if len(records) < 30:
        raise ValueError("FORTALEZA_GALLERY_TOO_FEW_VALID_RECORDS")
    return records


def fortaleza_annual_exercise(artifact, name, first, last, locator):
    identifier = "municipal-executive:" + hash_content(["2304400", name])[:24]
    return {
        "institution_code": "municipal_government", "territory_code": "2304400",
        "municipality_ibge": "2304400", "represented_uf": "CE", "name": name,
        "person_id": identifier, "exercise_id": identifier + ":" + str(first),
        "year_start": first, "year_end": last, "date_precision": "year",
        "political_party_code": None, "political_party_status": "unknown",
        "canonical_person_id": None, "source_url": artifact.resource.url,
        "territory_identity_basis": "present_day_ibge_index_for_historical_named_city",
        "territorial_boundaries_reconstructed": False,
        "evidence": [evidence(artifact, locator + " | " + name)],
        "coverage": "documented_partial",
    }
