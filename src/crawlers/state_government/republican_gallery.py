"""Parse Paraná's official gallery, distinguishing vice-office from executive exercise."""

import re
from datetime import date, timedelta

from crawlers.state_government.parsing import evidence, source_exercise, visible_text

BLOCK = re.compile(r"(?m)^\d{2,3}\s*-\s*(.+?)\s*$")
PERIOD = re.compile(r"^(\d{2}\.\d{2}\.\d{4}) a (\d{2}\.\d{2}\.\d{4})$")
ROLE = re.compile(
    r"^(?:Vice-|Governador|Governadora|Presidente do Estado|Interventor|Membro da Junta)"
)


def parse_parana_republican_gallery(artifact):
    text = visible_text(artifact.path.read_bytes())
    if "Período Republicano - 1889 a 2022" not in text:
        raise ValueError("PARANA_GALLERY_COVERAGE_CHANGED")
    headers = list(BLOCK.finditer(text))
    records, reviews = [], []
    for index, header in enumerate(headers):
        end = headers[index + 1].start() if index + 1 < len(headers) else len(text)
        block = text[header.end():end].split("Compartilhe:")[0]
        parsed, rejected = parana_gallery_block(header[1], block, artifact)
        records.extend(parsed)
        reviews.extend(rejected)
    if len(records) < 20:
        raise ValueError("PARANA_GALLERY_TOO_FEW_VALID_RECORDS")
    return records, reviews


def parana_gallery_block(name, block, artifact):
    lines = [line.strip() for line in block.splitlines() if line.strip()]
    roles = [line for line in lines if ROLE.match(line)]
    periods = [line for line in lines if PERIOD.fullmatch(line)]
    if not roles or not periods:
        return [], [{"name": name, "reason": "uncertain_dates_or_open_vice_office", "text": block}]
    if len(roles) == 1:
        roles *= len(periods)
    if len(roles) != len(periods):
        return [], [{"name": name, "reason": "role_period_alignment_ambiguous", "text": block}]
    records, reviews = [], []
    for role, period in zip(roles, periods, strict=True):
        if role.startswith(("Vice-", "Membro da Junta")):
            reviews.append({"name": name, "reason": "vice_or_collective_not_individual_exercise"})
            continue
        records.append(parana_gallery_exercise(name, role, period, artifact))
    return records, reviews


def parana_gallery_exercise(name, role, period, artifact):
    tokens = PERIOD.fullmatch(period).groups()
    start, end = [date.fromisoformat("-".join(token.split(".")[::-1])) for token in tokens]
    if (end.month, end.day) == (12, 31):
        end += timedelta(days=1)
    if end <= start:
        raise ValueError("PARANA_GALLERY_INVALID_INTERVAL")
    record = source_exercise(name, "PR", name)
    record.update(starts_on=str(start), ends_before=str(end), date_precision="day",
                  exercise_id=record["person_id"] + ":" + str(start),
                  exercise_kind=("temporary" if "Substituto" in role or "Interino" in role
                                 else "holder"),
                  source_office_code=role, source_url=artifact.resource.url,
                  boundary_semantics="transfer_dates_exclusive_calendar_december31_inclusive",
                  observed_through=None,
                  evidence=[evidence(artifact, name + " | " + role + " | " + period)])
    return record
