"""Reconcile reviewed ALESP exercise intervals. Preview by default."""

import argparse
import json
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from database.operations import PROJECT_ROOT, connect_database
from storage.files import hash_content

DEFAULT_EVIDENCE = PROJECT_ROOT / "data/enrichment/audits/alesp-posses-20-legislatura.json"
ENTRY_EVENTS = {"posse_confirmada", "reentrada_confirmada", "reentrada_data_efetiva_em_ato"}
EXIT_EVENTS = {"afastamento", "fim_exercicio"}


def load_evidence(path):
    evidence = json.loads(path.read_text(encoding="utf-8"))
    if evidence["legislature"] != 20:
        raise ValueError("Expected the 20th ALESP legislature")
    people = evidence["people"]
    identities = [str(UUID(person["person_id"])) for person in people]
    if len(set(identities)) != len(people):
        raise ValueError("Duplicate person in evidence")
    return people


def validated_events(person):
    events = sorted(person["events"], key=lambda event: event["date"])
    days = set()
    for event in events:
        day = date.fromisoformat(event["date"])
        url = urlsplit(event["source_url"])
        if (
            url.scheme != "https"
            or url.netloc not in {"www.al.sp.gov.br", "al.sp.gov.br", "www3.al.sp.gov.br"}
            or event["kind"] not in ENTRY_EVENTS | EXIT_EVENTS
            or day in days
            or not event["source_name"].strip()
        ):
            raise ValueError("Ambiguous event or invalid official evidence")
        days.add(day)
    return events


def exercise_intervals(events, current):
    intervals = []
    entry = None
    for event in events:
        if event["kind"] in ENTRY_EVENTS:
            if entry:
                raise ValueError("Consecutive entries require a documented interruption")
            entry = event
        else:
            if not entry:
                raise ValueError("Exit without a documented entry")
            intervals.append((entry, event))
            entry = None
    if entry and current and entry.get("continuity_verified_through"):
        review_day = date.fromisoformat(entry["continuity_verified_through"])
        if review_day >= current:
            intervals.append((entry, None))
    return intervals


def find_term(connection, person):
    terms = connection.execute(
        """
        SELECT t.id, t.term_start, t.term_end, p.has_current_public_office,
          p.current_public_office_term_id, current_date AS as_of
        FROM se_liga_brasil.office_term t
        JOIN se_liga_brasil.institution i ON i.id=t.institution_id
        JOIN se_liga_brasil.person p ON p.id=t.person_id
        WHERE p.id=%s AND p.civil_name=%s AND i.code='alesp'
          AND t.legislature_key='20' AND t.office_kind='state_deputy'
          AND NOT EXISTS(SELECT 1 FROM se_liga_brasil.person_identity_alias a
                         WHERE a.alias_person_id=p.id)
        """,
        (person["person_id"], person["civil_name"]),
    ).fetchall()
    return terms[0] if len(terms) == 1 else None


def save_evidence(connection, external_key, event, payload):
    source_record = connection.execute(
        """
        INSERT INTO se_liga_brasil.source_record
          (source_id,external_key,source_url,content_sha256,effective_at,payload)
        SELECT id,%s,%s,%s,%s::date,%s FROM se_liga_brasil.source WHERE code='alesp'
        ON CONFLICT(source_id,external_key,content_sha256)
          DO UPDATE SET source_url=excluded.source_url
        RETURNING id
        """,
        (
            external_key, event["source_url"],
            hash_content(payload), event["date"], Jsonb(payload),
        ),
    ).fetchone()
    if source_record is None:
        raise ValueError("ALESP source is missing")
    return source_record["id"]


def save_interval(connection, person, term_id, entry, exit_event, capacity):
    payload = {"person_id": person["person_id"], "entry": entry, "exit": exit_event}
    source_id = save_evidence(
        connection, f"exercise:{person['person_id']}:{entry['date']}", entry, payload
    )
    connection.execute(
        """
        INSERT INTO se_liga_brasil.office_exercise
          (term_id,starts_on,ends_before,capacity,source_record_id)
        VALUES (%s,%s,%s,%s,%s)
        """,
        (term_id, entry["date"], exit_event["date"] if exit_event else None,
         capacity, source_id),
    )


def save_inauguration(connection, person, event):
    payload = {
        "person_id": person["person_id"],
        "institution": "alesp",
        "legislature": 20,
        "event": event,
    }
    source_id = save_evidence(
        connection, f"inauguration:{person['person_id']}:{event['date']}", event, payload
    )
    inserted = connection.execute(
        """
        INSERT INTO se_liga_brasil.person_fact
          (person_id,field_name,original_value,normalized_value,
           evidence_kind,review_status,source_record_id)
        VALUES (%s,'alesp_inauguration',%s,%s,'administrative','verified',%s)
        ON CONFLICT(person_id,field_name,source_record_id) DO NOTHING
        """,
        (person["person_id"], Jsonb(payload), Jsonb(payload), source_id),
    ).rowcount
    return "inserted" if inserted else "already_present"


def reconcile_inaugurations(connection, person, apply):
    term = find_term(connection, person)
    if term is None:
        return {"status": "term_missing_or_ambiguous"}
    events = []
    for event in validated_events(person):
        if event["kind"] not in {"posse_confirmada", "reentrada_confirmada"}:
            continue
        day = date.fromisoformat(event["date"])
        if day > term["as_of"]:
            events.append(event | {"status": "future_event"})
            continue
        outside_term = (term["term_start"] and day < term["term_start"]) or (
            term["term_end"] and day >= term["term_end"]
        )
        status = save_inauguration(connection, person, event) if apply else "eligible"
        events.append(event | {"status": status, "term_dates_conflict": bool(outside_term)})
    return {"status": "inaugurations_reviewed", "events": events}


def reconcile_person(connection, person, apply):
    term = find_term(connection, person)
    if term is None:
        return {"status": "term_missing_or_ambiguous"}
    is_current = (
        term["has_current_public_office"] and term["current_public_office_term_id"] == term["id"]
    )
    try:
        events = validated_events(person)
        intervals = exercise_intervals(events, term["as_of"] if is_current else None)
    except ValueError as error:
        return {"status": "event_review_required", "reason": str(error)}
    results = [
        reconcile_interval(connection, person, term, entry, exit_event, apply)
        for entry, exit_event in intervals
    ]
    return {
        "status": "intervals_reviewed" if results else "continuity_review_required",
        "intervals": results,
        "current_start_verified": any(
            row["ends_before"] is None
            and row["status"] in {"eligible", "inserted", "already_present"}
            for row in results
        ),
    }


def reconcile_interval(connection, person, term, entry, exit_event, apply):
    start = date.fromisoformat(entry["date"])
    end = date.fromisoformat(exit_event["date"]) if exit_event else None
    result = {"starts_on": start, "ends_before": end}
    capacity = entry.get("capacity") or ("holder" if entry["date"] == "2023-03-15" else None)
    if capacity not in {"holder", "substitute"}:
        return result | {"status": "capacity_review_required"}
    if (term["term_start"] and start < term["term_start"]) or (
        term["term_end"] and (start >= term["term_end"] or (end and end > term["term_end"]))
    ) or start > term["as_of"]:
        return result | {"status": "outside_term"}
    overlaps = connection.execute(
        """
        SELECT starts_on,ends_before,capacity FROM se_liga_brasil.office_exercise
        WHERE term_id=%s AND daterange(starts_on,ends_before,'[)') && daterange(%s,%s,'[)')
        """,
        (term["id"], start, end),
    ).fetchall()
    if overlaps:
        exact = overlaps == [{"starts_on": start, "ends_before": end, "capacity": capacity}]
        return result | {"status": "already_present" if exact else "existing_interval_conflict"}
    if apply:
        save_interval(connection, person, term["id"], entry, exit_event, capacity)
    return result | {"status": "inserted" if apply else "eligible"}


def reconcile_current_exercise(connection, person, apply):
    candidate = person.get("current_exercise_start_candidate")
    entry_kind = reviewed_current_entry_kind(person)
    if not candidate or not entry_kind:
        return {"status": "current_start_unverified"}
    term = find_term(connection, person)
    if not term or not term["has_current_public_office"] or (
        term["current_public_office_term_id"] != term["id"]
    ):
        return {"status": "current_alesp_term_unverified"}
    roster = person.get("roster_observation", {})
    if roster.get("status") != "EXE" or (
        str(roster.get("alesp_subject_id")) not in person.get("alesp_subject_ids", [])
    ):
        return {"status": "roster_identity_unverified"}
    entries = [
        event for event in validated_events(person)
        if event["date"] == candidate and event["kind"] == entry_kind
    ]
    if len(entries) != 1 or any(event["date"] > candidate for event in person["events"]):
        return {"status": "event_review_required"}
    entry = entries[0] | {"capacity": person.get("current_exercise_capacity"),
                         "capacity_source_url": person.get("capacity_source_url")}
    if entry_kind == "posse_confirmada":
        entry["continuity_review"] = person["continuity_evidence"]["second_nominal_search"]
    result = reconcile_interval(connection, person, term, entry, None, apply)
    if apply and result["status"] in {"inserted", "already_present"}:
        result["resolved_gaps"] = resolve_current_exercise_gap(connection, person)
    return result


def reviewed_current_entry_kind(person):
    if person.get("review_status") == "official_effective_reentry":
        return "reentrada_data_efetiva_em_ato"
    if person.get("review_status") != "no_interruption_found_after_second_search":
        return None
    continuity = person.get("continuity_evidence", {})
    search = continuity.get("second_nominal_search", {})
    if continuity.get("interruptions") == [] and search.get("interruption_found") is False:
        return "posse_confirmada"
    return None


def resolve_current_exercise_gap(connection, person):
    return connection.execute(
        """
        UPDATE se_liga_brasil.person_data_gap
        SET status='resolved',quality_state='resolved',resolved_at=now(),
          is_processed=true,processed_at=now(),last_checked_at=now(),
          last_assessment_id=%s,claimed_by=NULL,lease_until=NULL
        WHERE person_id=%s AND field_name='current_office_started_on'
          AND assigned_source='alesp' AND status IN ('queued','blocked')
        """,
        (uuid4(), person["person_id"]),
    ).rowcount


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--apply", action="store_true")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--inaugurations-only", action="store_true")
    modes.add_argument("--current-exercise", action="store_true")
    arguments = parser.parse_args()
    people = load_evidence(arguments.evidence)
    reconcile = reconcile_person
    if arguments.inaugurations_only:
        reconcile = reconcile_inaugurations
    elif arguments.current_exercise:
        reconcile = reconcile_current_exercise
    with connect_database(arguments.env_file) as connection, connection.transaction():
        if arguments.apply:
            connection.execute("SET LOCAL lock_timeout='10s'")
            if not arguments.inaugurations_only:
                connection.execute(
                    "LOCK TABLE se_liga_brasil.office_exercise IN SHARE ROW EXCLUSIVE MODE"
                )
        else:
            connection.execute("SET TRANSACTION READ ONLY")
        report = [
            {"person_id": person["person_id"], "civil_name": person["civil_name"]}
            | reconcile(connection, person, arguments.apply)
            for person in people
        ]
    print(json.dumps(
        {"applied": arguments.apply, "people": report}, default=str, ensure_ascii=False, indent=2
    ))


if __name__ == "__main__":
    main()
