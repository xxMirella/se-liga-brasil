"""Merge dated government observations without replacing documented exercise intervals."""

import json


def merge_executive_observations(existing, incoming):
    if not existing or is_dated_observation_partition(existing):
        return {**incoming, "aggregation_basis": "dated_official_government_observations"}
    merged = dict(existing)
    events = list(existing.get("national_observations", []))
    events.extend(incoming.get("segments", []))
    unique = {}
    for event in events:
        identity = json.dumps(event, sort_keys=True, ensure_ascii=False)
        unique[identity] = event
    merged["national_observations"] = [unique[key] for key in sorted(unique)]
    return merged


def is_dated_observation_partition(partition):
    segments = partition.get("segments", [])
    return (
        bool(segments)
        and not partition.get("current")
        and all(
            segment.get("source_observed_on") and segment.get("date_precision") == "year"
            for segment in segments
        )
    )
