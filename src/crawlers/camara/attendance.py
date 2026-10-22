"""Parse official daily plenary frequency without counting session rows twice."""

import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

from parsing.html import HtmlTableParser, decode_html
from service.ingestion.contracts import IngestionError


def parse_attendance_days(payload, year, as_of):
    parser = HtmlTableParser(None)
    parser.feed(decode_html(payload))
    days = {}
    reported_total = None
    for row in parser.rows:
        if row[0] == "Total de dias com sessões deliberativas realizadas no período":
            reported_total = int(row[1])
        match = re.match(r"^(\d{2}/\d{2}/\d{4})\b", row[0])
        if not match:
            continue
        day = datetime.strptime(match[1], "%d/%m/%Y").date()
        if day.year != year or day > as_of:
            raise IngestionError("CAMARA_ATTENDANCE_DATE_OUTSIDE_PERIOD")
        status = attendance_status(row[-1])
        if day in days and days[day] != status:
            raise IngestionError("CAMARA_ATTENDANCE_CONFLICTING_DAY")
        days[day] = status
    if reported_total is None or len(days) != reported_total:
        raise IngestionError("CAMARA_ATTENDANCE_INCOMPLETE_DAYS")
    return days


def attendance_status(value):
    value = " ".join(value.casefold().split())
    if value == "presença":
        return "present"
    if "não justificad" in value:
        return "unexcused_absence"
    if "justificad" in value:
        return "excused_absence"
    return "unknown"


def collect_person_attendance(
    acquisition, repository, member, person_id, year, as_of=None, starts_on=None,
):
    from crawlers.camara.configuration import PORTAL_BASE
    from crawlers.camara.pipeline import ingest_collected
    from service.attendance.monthly import consolidate_monthly_attendance

    as_of = as_of or datetime.now(ZoneInfo("America/Belem")).date()
    url = f"{PORTAL_BASE}{member['id']}/presenca-plenario/{year}"
    artifact = acquisition.acquire(url, "camara_attendance", ".html")
    days = parse_attendance_days(artifact.path.read_bytes(), year, as_of)
    if starts_on:
        days = {day: status for day, status in days.items() if day >= starts_on}
    rows = consolidate_monthly_attendance(days, person_id, artifact, as_of)
    return {"months": len(rows), "days": len(days),
            **ingest_collected(repository, acquisition, artifact, rows)}


def collect_attendance_history(acquisition, repository, member, person_id, years=None):
    as_of = datetime.now(ZoneInfo("America/Belem")).date()
    # Earlier terms may not yet have been projected. Ask the source for all years.
    starts_on = date(max(2000, member.get("attendance_start_year", 2000)), 1, 1)
    requested = validate_attendance_years(years, starts_on.year, as_of.year)
    collected = []
    failures = []
    for year in requested:
        try:
            result = collect_person_attendance(
                acquisition, repository, member, person_id, year, as_of, starts_on,
            )
            collected.append({"year": year, **result})
        except IngestionError as error:
            if error.code == "SOURCE_COOLDOWN_ACTIVE" or error.details.get("status") in {
                403, 429, 500, 502, 503, 504,
            }:
                raise
            failures.append({"year": year, "code": error.code})
    return {"search_starts_on": starts_on.isoformat(), "years": collected, "failures": failures}


def validate_attendance_years(years, first_year, current_year):
    if years is None:
        return list(range(current_year, first_year - 1, -1))
    selected = sorted(set(years), reverse=True)
    if not selected or len(selected) > current_year - 1999 or any(
        type(year) is not int or not 2000 <= year <= current_year for year in selected
    ):
        raise IngestionError("INVALID_ATTENDANCE_YEARS")
    return [year for year in selected if year >= first_year]
