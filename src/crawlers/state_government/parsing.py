"""Read official chronology and external-mandate biographies without current-party leakage."""

import re
from datetime import date, timedelta

from parsing.html import HtmlTableParser, decode_html
from parsing.visible_text import extract_visible_text
from service.ingestion.contracts import IngestionError
from storage.files import hash_content

DATE_TOKEN = re.compile(r"(?<!\d)(\d{2})[/.](\d{2})[/.](\d{4})(?!\d)")
GOVERNOR_MANDATE = re.compile(
    r"(?<!Vice-)Governador\(a\),\s*(?P<uf>[A-Z]{2}),\s*"
    r"(?:Partido:\s*(?P<political_party>[^,;]+),\s*)?"
    r"Período:\s*(?P<start>\d{4})(?:\s*a\s*(?P<end>\d{4}))?",
    re.I,
)


def source_html(payload):
    if re.search(rb'charset\s*=\s*["\']?ISO-8859-1', payload[:2000], re.I):
        return payload.decode("latin1")
    if re.search(rb"charset\s*=\s*[\"\']?windows-1252", payload[:2000], re.I):
        return payload.decode("cp1252", errors="replace")
    return decode_html(payload)


def visible_text(payload):
    return extract_visible_text(source_html(payload))


def evidence(artifact, locator):
    return {
        "url": artifact.resource.url,
        "sha256": artifact.sha256,
        "fetched_at": artifact.fetched_at,
        "locator": locator,
    }


def source_exercise(name, uf, source_key):
    return {
        "institution_code": "state_government",
        "territory_code": uf,
        "name": name,
        "person_id": "state-executive:" + hash_content([uf, source_key])[:24],
        "political_party_code": None,
        "political_party_status": "unknown",
        "canonical_person_id": None,
        "coverage": "documented_partial",
        "evidence": [],
    }


def parse_chronology_row(cells, artifact, observed_through):
    if len(cells) != 2:
        return None
    dates = [
        date(int(year), int(month), int(day)) for day, month, year in DATE_TOKEN.findall(cells[0])
    ]
    name = re.match(r"(.+?)\s*-\s*([A-Z][A-Z/]*|Substituto do IF)\b", cells[1])
    if not name or not dates or dates[0].year > 2200:
        return None
    temporary = cells[0].strip().startswith("(")
    ends_before = dates[1] if len(dates) == 2 else None
    if temporary or ends_before == dates[0]:
        ends_before = (ends_before or dates[0]) + timedelta(days=1)
    result = source_exercise(name[1].strip(), "SP", name[1].strip())
    result.update(
        starts_on=dates[0].isoformat(),
        ends_before=ends_before.isoformat() if ends_before else None,
        date_precision="day",
        exercise_kind="temporary" if temporary else "holder",
        source_office_code=name[2].strip(),
        source_url=artifact.resource.url,
        observed_through=observed_through,
        evidence=[evidence(artifact, " | ".join(cells))],
    )
    return result


def parse_alesp_governor_chronology(artifact, require_update=True):
    html = source_html(artifact.path.read_bytes())
    updated = re.search(r"Atualizado em\s*(\d{2})/(\d{2})/(\d{4})", html)
    if not updated and require_update:
        raise IngestionError("STATE_GOVERNMENT_CHRONOLOGY_UPDATE_MISSING")
    observed_through = (
        date(int(updated[3]), int(updated[2]), int(updated[1])).isoformat() if updated else None
    )
    parser = HtmlTableParser(None)
    parser.feed(html)
    exercises = [
        record
        for cells in parser.rows
        if (record := parse_chronology_row(cells, artifact, observed_through))
    ]
    if not exercises:
        raise IngestionError("STATE_GOVERNMENT_CHRONOLOGY_MISSING")
    return exercises


def parse_external_governor_mandates(artifact, name, minimum_year=2000):
    page = visible_text(artifact.path.read_bytes())
    if "Mandatos Externos:" not in page:
        raise IngestionError("STATE_GOVERNMENT_EXTERNAL_MANDATES_MISSING")
    section = page.partition("Mandatos Externos:")[2].partition("Atividades Profissionais")[0]
    records = []
    for match in GOVERNOR_MANDATE.finditer(section):
        first, last = int(match["start"]), int(match["end"] or match["start"])
        if last < minimum_year:
            continue
        record = source_exercise(name, match["uf"], name)
        record.update(
            year_start=first,
            year_end=last,
            starts_on=None,
            ends_before=None,
            date_precision="year",
            source_url=artifact.resource.url,
            evidence=[evidence(artifact, match[0])],
        )
        if match["political_party"]:
            abbreviation = match["political_party"].strip()
            record.update(
                political_party_observations=[
                    {
                        "abbreviation": abbreviation,
                        "context": "external_mandate_biography_not_continuous_affiliation",
                        "year_start": first,
                        "year_end": last,
                        "evidence": [evidence(artifact, match[0])],
                    }
                ],
            )
        records.append(record)
    return records


def parse_alesp_provisional_triumvirate(artifact):
    parser = HtmlTableParser(None)
    parser.feed(source_html(artifact.path.read_bytes()))
    names = ("Prudente José de Moraes Barros", "Francisco Rangel Pestana", "Joaquim de Souza Mursa")
    candidates = [
        row for row in parser.rows if len(row) == 2 and row[0].strip() == "16/11/1889 a 14/12/1889"
    ]
    if len(candidates) != 1 or not all(name in candidates[0][1] for name in names):
        raise IngestionError("STATE_GOVERNMENT_PROVISIONAL_TRIUMVIRATE_MISSING")
    records = []
    for name in names:
        record = source_exercise(name, "SP", name)
        record.update(
            starts_on="1889-11-16",
            ends_before="1889-12-14",
            date_precision="day",
            exercise_kind="provisional_collective",
            source_url=artifact.resource.url,
            evidence=[evidence(artifact, " | ".join(candidates[0]))],
        )
        records.append(record)
    return records
