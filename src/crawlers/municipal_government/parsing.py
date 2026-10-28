"""Normalize documented municipal exercises; tenure precision is independent from party labels."""

import re
from datetime import date, timedelta

from crawlers.municipal_government.documents import document_text
from storage.files import hash_content

DATE_TOKEN = r"\d{2}/\d{2}/\d{4}"


def evidence(artifact, locator):
    return dict(
        url=artifact.resource.url,
        sha256=artifact.sha256,
        fetched_at=artifact.fetched_at,
        locator=locator,
    )


def municipal_exercise(name, territory_code, artifact, locator):
    return {
        "institution_code": "municipal_government",
        "territory_code": territory_code,
        "name": name,
        "person_id": "municipal-executive:" + hash_content([territory_code, name])[:24],
        "canonical_person_id": None,
        "political_party_code": None,
        "political_party_status": "unknown",
        "source_url": artifact.resource.url,
        "coverage": "documented_partial",
        "evidence": [evidence(artifact, locator)],
    }


def iso_date(value):
    day, month, year = map(int, value.split("/"))
    return date(year, month, day).isoformat()


def parse_sp_dossier(artifact):
    text = document_text(artifact)
    if "Atualizado até: 30/08/2023" not in text:
        raise ValueError("MUNICIPAL_GOVERNMENT_DOSSIER_VERSION_REQUIRES_REVIEW")
    section = text.partition("POR ORDEM CRONOLÓGICA DE MANDATO")[2]
    section = section.partition("LISTA DE PREFEITOS DA CIDADE DE SÃO PAULO POR ORDEM ALFABÉTICA")[0]
    starts = list(re.finditer(r"(?m)^\s*(\d{1,2})º\s*", section))
    records = []
    for index, match in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(section)
        block = section[match.end() : end]
        row = sp_dossier_row(block, artifact, match[1])
        if row["starts_on"] >= "1889-01-01":
            records.append(row)
    if len(starts) != 58 or len(records) != 55:
        raise ValueError("MUNICIPAL_GOVERNMENT_DOSSIER_ROW_COUNT_REQUIRES_REVIEW")
    return reconcile_documented_handover_dates(records)


def sp_dossier_row(block, artifact, ordinal):
    dates = list(re.finditer(DATE_TOKEN, block))
    if not dates:
        raise ValueError("MUNICIPAL_GOVERNMENT_DOSSIER_DATE_MISSING")
    name = " ".join(block[: dates[0].start()].partition("(")[0].split()).removesuffix(" Desde")
    row = municipal_exercise(name, "3550308", artifact, f"Chronological list; ordinal {ordinal}")
    row.update(
        starts_on=iso_date(dates[0][0]),
        ends_before=None,
        date_precision="day",
        exercise_kind="holder",
        observed_through="2023-08-30",
    )
    if "Desde" not in block[: dates[0].start()]:
        row["ends_before"] = (
            date.fromisoformat(iso_date(dates[1][0])) + timedelta(days=1)
        ).isoformat()
    return row


def reconcile_documented_handover_dates(records):
    for previous, successor in zip(records, records[1:], strict=False):
        end = previous["ends_before"]
        if (
            end
            and (date.fromisoformat(end) - timedelta(days=1)).isoformat() == successor["starts_on"]
        ):
            previous["ends_before"] = successor["starts_on"]
    return records


def parse_sp_dossier_interims(artifact):
    text = document_text(artifact)
    section = text.partition(
        "LISTA DE PREFEITOS INTERINOS DA CIDADE DE SÃO PAULO POR ORDEM ALFABÉTICA"
    )[2]
    section = section.partition(
        "LISTA DE PREFEITOS INTERINOS DA CIDADE DE SÃO PAULO POR ORDEM CRONOLÓGICA"
    )[0]
    records, current_name = [], None
    for original in section.splitlines():
        line = original.strip().lstrip("\f")
        if (
            not line
            or line.startswith(("PREFEITOS INTERINOS", "(", "Das ", "às "))
            or re.match(r"^\d{1,2}h", line)
        ):
            continue
        match = re.search(DATE_TOKEN, line)
        prefix = line[: match.start()].strip() if match else line
        if prefix and not prefix.startswith(
            ("Vice-", "Presidente da Câmara", "Secretário", "do Interior")
        ):
            current_name = prefix.removesuffix(" OK")
        if match and current_name:
            record = sp_interim_row(line, current_name, artifact)
            if record["starts_on"] >= "1889-01-01":
                records.append(record)
    return records


def sp_interim_row(line, name, artifact):
    dates = re.findall(DATE_TOKEN, line)
    row = municipal_exercise(name, "3550308", artifact, "Interim alphabetical list: " + line)
    end = date.fromisoformat(iso_date(dates[1] if len(dates) > 1 else dates[0]))
    row.update(
        starts_on=iso_date(dates[0]),
        ends_before=(end + timedelta(days=1)).isoformat(),
        date_precision="day",
        exercise_kind="temporary",
    )
    return row
