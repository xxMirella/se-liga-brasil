from datetime import date

from service.enrichment.completeness import build_completeness_report, evaluate_person_completeness


def person_row(**changes):
    return {
        "person_id": "p",
        "civil_name": "Pessoa Fictícia",
        "birth_date": date(1980, 1, 1),
        "education_level": "SUPERIOR COMPLETO",
        "current_party": False,
        "current_office": None,
        "latest_payroll": None,
        "latest_election": 2026,
        "latest_assets": None,
        "reported_no_assets": False,
        "has_propositions": False,
    } | changes


def test_missing_payroll_and_assets_are_not_zero_or_not_applicable():
    result = evaluate_person_completeness(person_row(), date(2026, 10, 17))
    assert result["fields"]["current_salary"] == "missing"
    assert result["fields"]["declared_assets"] == "missing"
    assert not result["complete"]


def test_authorship_presence_does_not_prove_historical_activity_coverage():
    result = evaluate_person_completeness(person_row(has_propositions=True), date(2026, 10, 17))
    assert result["has_propositions"] is True
    assert result["fields"]["political_activity"] == "partial"


def test_previous_election_assets_do_not_fill_latest_declaration_gap():
    result = evaluate_person_completeness(person_row(latest_assets=2022), date(2026, 10, 17))
    assert result["fields"]["declared_wealth"] == "missing"
    no_assets = person_row(latest_assets=2022, reported_no_assets=True)
    assert (
        evaluate_person_completeness(no_assets)["fields"]["declared_assets"] == "reported_no_assets"
    )


def test_latest_published_month_is_current_but_old_payment_is_outdated():
    current = person_row(latest_payroll=date(2026, 9, 1))
    old = person_row(latest_payroll=date(2026, 8, 1))
    assert (
        evaluate_person_completeness(current, date(2026, 10, 17))["fields"]["current_salary"]
        == "present"
    )
    assert (
        evaluate_person_completeness(old, date(2026, 10, 17))["fields"]["current_salary"]
        == "outdated"
    )
    assert build_completeness_report([current, old], date(2026, 10, 17))["total_people"] == 2


def test_backfill_scope_depends_on_internal_targets_not_only_election():
    from pathlib import Path

    from crawlers.tse.enrichment import AssetBackfillConfiguration

    first = AssetBackfillConfiguration(storage_directory=Path("/tmp"), target_person_ids=("p1",))
    second = AssetBackfillConfiguration(storage_directory=Path("/tmp"), target_person_ids=("p2",))
    assert first.scope_key != second.scope_key


def test_verified_absence_resolves_office_without_inventing_salary():
    result = evaluate_person_completeness(person_row(current_office=False))
    assert result["fields"]["current_public_office"] == "confirmed_no_current_office"
    assert result["fields"]["current_salary"] == "not_applicable"


def test_attendance_without_official_records_is_missing_even_with_propositions():
    result = evaluate_person_completeness(
        person_row(current_office=True, has_propositions=True), date(2026, 10, 19)
    )
    assert result["fields"]["attendance"] == "missing_or_unverified"
    assert build_completeness_report(
        [person_row(current_office=True)], date(2026, 10, 19)
    )["missing_by_field"]["attendance"] == 1


def test_attendance_latest_closed_month_is_present_but_older_month_is_outdated():
    current = person_row(current_office=True, latest_attendance_period=date(2026, 9, 1))
    outdated = person_row(current_office=True, latest_attendance_period=date(2026, 8, 1))
    assert evaluate_person_completeness(current, date(2026, 10, 19))["fields"]["attendance"] == (
        "present"
    )
    assert evaluate_person_completeness(outdated, date(2026, 10, 19))["fields"]["attendance"] == (
        "outdated"
    )


def test_attendance_unknown_days_keep_latest_period_partial():
    row = person_row(
        current_office=True, latest_attendance_period=date(2026, 9, 1), attendance_unknown=2
    )
    assert evaluate_person_completeness(row, date(2026, 10, 19))["fields"]["attendance"] == (
        "partial"
    )


def test_confirmed_absence_of_current_office_does_not_require_current_attendance():
    row = person_row(current_office=False, attendance_unknown=2)
    assert evaluate_person_completeness(row, date(2026, 10, 19))["fields"]["attendance"] == (
        "not_applicable"
    )


def test_attendance_threshold_crosses_year_boundary_correctly():
    row = person_row(current_office=True, latest_attendance_period=date(2025, 12, 1))
    assert evaluate_person_completeness(row, date(2026, 1, 1))["fields"]["attendance"] == (
        "present"
    )


def test_photo_is_required_and_not_satisfied_by_complete_textual_identity():
    row = person_row()
    assert evaluate_person_completeness(row)["fields"]["photo_url"] == "missing"
    assert build_completeness_report([row])["missing_by_field"]["photo_url"] == 1
    row["photo_url"] = "https://www.camara.leg.br/photo.jpg"
    assert evaluate_person_completeness(row)["fields"]["photo_url"] == "present"


def test_verified_current_office_still_requires_individual_exercise_start():
    result = evaluate_person_completeness(person_row(current_office=True))
    assert result['fields']['current_office_started_on'] == 'missing_or_unverified'
    row = person_row(current_office=True, current_office_started_on=date(2023, 2, 1))
    assert evaluate_person_completeness(row)['fields']['current_office_started_on'] == 'present'
    row = person_row(current_office=False)
    assert (
        evaluate_person_completeness(row)['fields']['current_office_started_on']
        == 'not_applicable'
    )
