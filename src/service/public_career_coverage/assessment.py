"""Application entry point: canonical batch reads followed by pure partition planning."""

from database.career_coverage import fetch_career_coverage_inputs, fetch_coverage_receipts
from service.public_career_coverage.planning import (
    build_activity_scopes,
    build_observed_scopes,
    plan_coverage,
)


def assess_career_coverage(connection, person_ids, today, receipts=(), expected_scopes=()):
    facts = fetch_career_coverage_inputs(connection, person_ids)
    scopes = build_observed_scopes(facts["candidacies"], facts["exercises"], today)
    scopes.update(build_activity_scopes(scopes))
    scopes.update(expected_scopes)
    receipts = tuple(receipts) + tuple(fetch_coverage_receipts(connection, person_ids))
    plan = plan_coverage(scopes, receipts, today)
    return plan | {"known_terms": facts["terms"], "career_beginning_verified": False}


def select_shared_tse_resources(plan, catalog_resources):
    """Resolve existing discovery Resource objects; nationwide archives download once."""
    people_by_year = {}
    people_by_partition = {}
    for request in plan["resources"]:
        if request.source != "tse" or request.domain != "elections":
            continue
        year, uf = request.partition.split("/", 1)
        people_by_year.setdefault(int(year), set()).update(request.person_ids)
        people_by_partition.setdefault((int(year), uf), set()).update(request.person_ids)
    selected = {}
    for resource in catalog_resources:
        if resource.kind not in {"candidate", "complement", "history"}:
            continue
        people = (
            people_by_partition.get((resource.year, resource.uf), set())
            if resource.uf
            else people_by_year.get(resource.year, set())
        )
        if people:
            entry = selected.setdefault(resource.url, {"resource": resource, "person_ids": set()})
            entry["person_ids"].update(people)
    return list(selected.values())
