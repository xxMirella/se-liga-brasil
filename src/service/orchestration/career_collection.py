"""Dispatch partition plans only for leased tasks from the existing durable gap queue."""

from itertools import islice

from database.career_coverage import MAX_CAREER_BATCH, persist_coverage_receipts
from service.public_career_coverage.assessment import assess_career_coverage


def dispatch_career_resources(connection, tasks, today, collectors, max_resources=10):
    """Callbacks receive one shared resource and must reuse source cache/cooldown policy.

    Caller owns queue leases and source locks. Callbacks return explicit receipts;
    missing collectors remain pending and cannot certify successful enumeration.
    """
    if not 1 <= max_resources <= 100:
        raise ValueError("Invalid career resource budget")
    people = list(
        dict.fromkeys(
            task["person_id"] for task in tasks if task["field_name"] == "political_activity"
        )
    )
    if not people:
        return {"resources": 0, "receipts": 0, "unsupported": []}
    plan = assess_career_coverage(connection, people, today)
    resources = [
        item for item in plan["resources"] if item.domain in {"propositions", "votes", "laws"}
    ]
    resources.sort(key=lambda item: item.partition.split("/")[-1], reverse=True)
    unsupported, persisted, attempted = [], 0, 0
    for resource in resources:
        channel = resource.partition.split("/")[0]
        collector = collectors.get((resource.source, resource.domain, channel)) or collectors.get(
            (resource.source, resource.domain)
        )
        if collector is None:
            unsupported.append((resource.source, resource.domain, resource.partition))
            continue
        if attempted >= max_resources:
            break
        attempted += 1
        receipts = tuple(islice(collector(resource), MAX_CAREER_BATCH + 1))
        if len(receipts) > MAX_CAREER_BATCH:
            raise ValueError("Receipt batch exceeds 1000 records")
        validate_dispatched_receipts(resource, receipts, plan["assessments"])
        persisted += persist_coverage_receipts(connection, receipts)
    return {
        "resources": len(resources),
        "attempted": attempted,
        "receipts": persisted,
        "unsupported": unsupported,
        "deferred": len(resources) - len(unsupported) - attempted,
    }


def validate_dispatched_receipts(resource, receipts, assessments):
    """A collector cannot certify people, partitions or intervals outside its request."""
    allowed = set(resource.person_ids)
    key = (resource.source, resource.institution, resource.domain, resource.partition)
    seen = set()
    for receipt in receipts:
        scope = receipt.scope
        actual = (scope.source, scope.institution, scope.domain, scope.partition)
        if actual != key or scope.person_id not in allowed or scope not in assessments:
            raise ValueError("Receipt outside dispatched scope")
        if scope in seen:
            raise ValueError("Duplicate receipt scope")
        seen.add(scope)
