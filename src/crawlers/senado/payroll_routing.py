"""Route salary-only requests through stored identity before requesting legislative profiles."""

from crawlers.senado.payroll_acquisition import previous_payroll_period
from crawlers.senado.payroll_collection import collect_stored_profile_salaries
from database.senado_payroll import fetch_verified_payroll_profiles
from service.observability.reporting import describe_error


def collect_with_verified_salary_profiles(repository, acquisition, people, collect_profiles):
    salary_ids = {
        person["person_id"] for person in people
        if set(person.get("requested_fields", [])) == {"current_salary"}
    }
    if not salary_ids:
        return collect_profiles(repository, acquisition, people)
    stored = fetch_verified_payroll_profiles(repository.connection, previous_payroll_period())
    selected = [profile for profile in stored if profile["personId"] in salary_ids]
    selected = selected[:acquisition.configuration.max_people]
    if not selected:
        return collect_profiles(repository, acquisition, people)
    result = collect_stored_profile_salaries(repository, acquisition, selected)
    selected_ids = {profile["personId"] for profile in selected}
    remaining = [person for person in people if person["person_id"] not in selected_ids]
    available = acquisition.configuration.max_people - len(selected)
    pending, deferred = remaining[:available], remaining[available:]
    result.update({
        "unmatched_person_ids": [],
        "deferred_person_ids": [person["person_id"] for person in deferred],
    })
    if pending:
        collect_remaining_profiles(repository, acquisition, pending, collect_profiles, result)
    result["deferred"] = len(result["deferred_person_ids"])
    return result


def collect_remaining_profiles(repository, acquisition, pending, collect_profiles, result):
    try:
        remaining = collect_profiles(repository, acquisition, pending)
        for field in ("people", "failures", "unmatched_person_ids", "deferred_person_ids"):
            result[field].extend(remaining[field])
    except Exception as error:
        result["failures"].append(describe_error(error))
        result["deferred_person_ids"].extend(person["person_id"] for person in pending)
