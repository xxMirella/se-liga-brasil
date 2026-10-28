"""Election observations enrich annual evidence without asserting seat composition."""

from collections import defaultdict
from copy import deepcopy

from service.political_dashboard_dataset.aggregation import build_annual_partition


def group_election_observations(observations):
    grouped = defaultdict(dict)
    for row in observations:
        if row["date_precision"] != "year":
            raise ValueError("SENATE_ELECTION_YEAR_PRECISION_REQUIRED")
        for territory in {"BR", row["territory_code"]}:
            key = row["election_year"], territory
            identity = row["source_event_id"]
            previous = grouped[key].get(identity)
            if previous and previous != row:
                raise ValueError("SENATE_ELECTION_SOURCE_EVENT_CONFLICT")
            grouped[key][identity] = row
    return grouped


def merge_senate_election_observations(existing, observations):
    indexed = {(row["year"], row["territory_code"]): row for row in existing}
    result = []
    for (year, territory), incoming in sorted(group_election_observations(observations).items()):
        partition = deepcopy(indexed.get(
            (year, territory), build_annual_partition([], year, territory, "senado"),
        ))
        previous = {row["source_event_id"]: row
                    for row in partition.get("election_observations", [])}
        previous.update(incoming)
        partition["election_observations"] = [previous[key] for key in sorted(previous)]
        result.append(partition)
    return result


def attach_senate_elections(partitions, observations):
    indexed = {(row["year"], row["territory_code"]): row for row in partitions}
    for row in merge_senate_election_observations(partitions, observations):
        indexed[row["year"], row["territory_code"]] = row
    return [indexed[key] for key in sorted(indexed)]
