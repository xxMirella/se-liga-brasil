"""Persist one gap per person/field; JSON reports are optional audit mirrors."""

from datetime import date
from itertools import batched

from database.completeness import fetch_completeness_rows
from database.data_gaps import persist_data_gaps
from database.public_office import refresh_current_public_offices
from service.completeness.rules import build_completeness_report
from service.maintenance.data_gap_cleanup import purge_processed_gaps
from service.public_career_coverage.assessment import assess_career_coverage
from service.public_career_coverage.planning import overlay_political_activity_coverage
from storage.files import save_json


def assess_completeness(connection, storage, person_id=None) -> dict:
    refresh_current_public_offices(connection)
    report = build_completeness_report(fetch_completeness_rows(connection, person_id))
    report = overlay_career_batches(connection, report, date.today())
    persistence = persist_data_gaps(connection, report)
    cleanup = purge_processed_gaps(connection)
    report_storage = storage / "people" / person_id if person_id else storage
    save_json(report_storage / "completeness.json", report)
    return {key: value for key, value in report.items() if key != "people"} | persistence | cleanup


def overlay_career_batches(connection, report, today):
    """Assess bounded fact batches, but persist only the complete report afterward."""
    assessments = {}
    for people in batched(report["people"], 1000):
        plan = assess_career_coverage(connection, [row["person_id"] for row in people], today)
        assessments.update(plan["assessments"])
    return overlay_political_activity_coverage(report, assessments)
