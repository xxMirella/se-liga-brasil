"""Parse dated synopsis narratives without inferring nominal ballots or authorship."""

import re
from datetime import date

from crawlers.alerj.parsing import parse_page, parse_profile_birth_date
from normalization.identity import normalize_person_name
from service.ingestion.contracts import IngestionError
from storage.files import hash_content

SESSION = re.compile(
    r"(?:Sessão\s+(?:Ordinária|Extraordinária)|Expediente\s+(?:Final|Inicial))\s*[–—-]\s*(\d{1,2})[ºª]?/(\d{2})/(\d{4})",
    re.I,
)
PROPOSITION = re.compile(
    r"Projeto de (Lei Complementar|Lei|Resolução|Decreto Legislativo)"
    r"\s*n[º°o.]?\s*([\d]+(?:-[A-Z])?)/(\d{4})",
    re.I,
)
KINDS = {"lei": "PL", "lei complementar": "PLC", "resolução": "PR", "decreto legislativo": "PDL"}


def parse_historical_profile(payload):
    page = parse_page(payload)
    text = "\n".join(line.strip() for line in "".join(page.text).splitlines() if line.strip())
    name = re.search(r"(?im)^DEPUTAD[OA]\s+([^\n]+)", text)
    if not name:
        raise IngestionError("ALERJ_HISTORICAL_PROFILE_NAME_MISSING")
    return {"displayName": name[1].strip(), "birthDate": parse_profile_birth_date(text)}


def classify_narrative(description):
    if re.search(r"(?:Registra seu voto|Declara as razões pelas quais votou)", description, re.I):
        return "vote_declaration"
    if re.match(
        r"(?:Encaminha|Solicita verificação|Requer|Solicita a retirada)", description, re.I
    ):
        return "voting_procedure"
    if re.match(r"(?:Discursa|Da Tribuna|Pela Ordem)", description, re.I):
        return "speech"
    return "legislative_comment"


def normalize_narrative(description, occurred_on, page_number, ordinal, source_url):
    description = " ".join(description.split())
    match = PROPOSITION.search(description)
    matter = None
    if match:
        kind, number, year = match.groups()
        matter = {"kind": KINDS[kind.casefold()], "number": number, "year": int(year)}
        matter["title"] = f"{matter['kind']} {number}/{year}"
    key = hash_content([source_url, page_number, occurred_on, ordinal, description])
    return {
        "eventKey": key,
        "occurredOn": occurred_on,
        "pdfPage": page_number,
        "eventType": classify_narrative(description),
        "description": description,
        "sourceUrl": source_url,
        "evidenceUrl": f"{source_url}#page={page_number}",
        "matter": matter,
        "nominalBallotVerified": False,
        "coverage": "partial_official_synopsis",
    }


def parse_synopsis_pages(pages, expected_name, source_url, year):
    records, rejected = [], []
    for page_number, page in enumerate(pages, 1):
        if not SESSION.search(page):
            continue
        names = re.findall(r"Deputad[oa]\s+([^\n]+)", page, re.I)
        if not names or normalize_person_name(names[0]) != normalize_person_name(expected_name):
            raise IngestionError("ALERJ_SYNOPSIS_PERSON_MISMATCH")
        accepted, failures = parse_session_page(page, page_number, source_url, year)
        records.extend(accepted)
        rejected.extend(failures)
    if not records:
        raise IngestionError("ALERJ_SYNOPSIS_NO_DATED_NARRATIVES")
    return records, rejected


def parse_session_page(page, page_number, source_url, year):
    records, rejected = [], []
    sessions = list(SESSION.finditer(page))
    for index, session in enumerate(sessions):
        day, month, session_year = map(int, session.groups())
        try:
            occurred = date(session_year, month, day)
            if occurred.year != year or occurred.year < 2000:
                raise ValueError("Outside document period")
        except ValueError:
            rejected.append(
                {"reasonCode": "ALERJ_SYNOPSIS_SESSION_DATE_INVALID", "page": page_number}
            )
            continue
        end = sessions[index + 1].start() if index + 1 < len(sessions) else len(page)
        body = page[session.end() : end]
        records.extend(parse_narrative_body(body, occurred.isoformat(), page_number, source_url))
    return records, rejected


def parse_narrative_body(body, occurred_on, page_number, source_url):
    body = re.sub(r"(?im)^\s*Páginas?\s+[^\n]+", "\n\n", body)
    body = re.split(r"ASSEMBL[ÉE]IA LEGISLATIVA", body, flags=re.I)[0]
    paragraphs = [value.strip() for value in re.split(r"\n\s*\n", body) if value.strip()]
    return [
        normalize_narrative(value, occurred_on, page_number, ordinal, source_url)
        for ordinal, value in enumerate(paragraphs)
        if re.search(r"[A-Za-zÀ-ÿ]{3}", value)
    ]
