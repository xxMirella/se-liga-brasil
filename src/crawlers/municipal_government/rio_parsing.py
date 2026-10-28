"""Read the city archive's municipal-era chronology; Guanabara governors are excluded."""

import json
import re

from crawlers.municipal_government.documents import document_text
from crawlers.municipal_government.parsing import municipal_exercise
from parsing.visible_text import extract_visible_text


def parse_rio_municipal_archive(artifact):
    text = document_text(artifact)
    records = []
    for match in re.finditer(r"(?m)^\s*(\d{4})(?:-(\d{4}))?\s+([^\n]+)$", text):
        first, last = int(match[1]), int(match[2] or match[1])
        if first < 1975 or last > 2016:
            continue
        name = match[3].partition("(")[0].strip()
        row = municipal_exercise(name, "3304557", artifact, match[0].strip())
        row.update(year_start=first, year_end=last, date_precision="year")
        records.append(row)
    if len(records) != 13:
        raise ValueError("MUNICIPAL_GOVERNMENT_RIO_ARCHIVE_ROWS_REQUIRE_REVIEW")
    return records


def parse_rio_crivella_and_succession(artifact):
    rows = json.loads(artifact.path.read_text(encoding="utf-8-sig"))
    candidates = [row for row in rows if row.get("ano") == "2020"]
    if len(candidates) != 1:
        raise ValueError("MUNICIPAL_GOVERNMENT_RIO_2020_NOT_FOUND")
    text = " ".join(extract_visible_text(candidates[0]["rio"]).split())
    required = (
        "é o prefeito (01/01/2017-22/12/2020)",
        "Jorge Felippe (DEM), assume como ‘prefeito em exercício’",
    )
    if not all(quote in text for quote in required):
        raise ValueError("MUNICIPAL_GOVERNMENT_RIO_SUCCESSION_NOT_FOUND")
    crivella = municipal_exercise(
        "Marcelo Bezerra Crivella", "3304557", artifact, "ano2020.rio: " + required[0]
    )
    crivella.update(starts_on="2017-01-01", ends_before="2020-12-22", date_precision="day")
    felippe = municipal_exercise(
        "Jorge Felippe", "3304557", artifact, "ano2020.rio: " + required[1]
    )
    felippe.update(
        starts_on="2020-12-22",
        ends_before=None,
        date_precision="day",
        observed_through="2020-12-22",
        exercise_kind="temporary",
    )
    return [crivella, felippe]


def official_rio_period(artifact, name, start, end, quote):
    if quote not in document_text(artifact):
        raise ValueError("MUNICIPAL_GOVERNMENT_RIO_ACCESSION_NOT_FOUND:" + name)
    row = municipal_exercise(name, "3304557", artifact, quote)
    row.update(
        starts_on=start,
        ends_before=end,
        date_precision="day",
        observed_through=start if not end else None,
    )
    return row
