"""Resumable acquisitions become validated yearly snapshots, never current-party backfills."""

from crawlers.senado.historical_parsing import (
    annual_senate_observations,
    parse_affiliations,
    parse_exercises,
)
from service.political_dashboard_dataset.aggregation import build_annual_partitions
from service.political_dashboard_dataset.storage import store_partition, write_atomic
from storage.files import save_json


def collect_exercises(acquisition, legislatures, progress):
    unique = {}
    coverage = []
    for legislature in legislatures:
        payload, evidence = acquisition.acquire(
            f"senador/lista/legislatura/{legislature}.json?exercicio=S"
        )
        exercises = parse_exercises(payload, evidence)
        coverage.append({"legislature": legislature, "exercises": len(exercises),
                         "evidence": evidence})
        for exercise in exercises:
            key = exercise["source_person_id"], exercise["exercise_id"]
            previous = unique.get(key)
            if previous and {k: v for k, v in previous.items() if k != "evidence"} != {
                k: v for k, v in exercise.items() if k != "evidence"
            }:
                raise ValueError("SENATE_EXERCISE_CONFLICT_BETWEEN_LEGISLATURES")
            unique[key] = exercise
        progress({"stage": "exercises", "legislature": legislature,
                  "unique_exercises": len(unique)})
    return list(unique.values()), coverage


def collect_affiliations(acquisition, exercises, progress):
    people = sorted({row["source_person_id"] for row in exercises})
    result = {}
    for index, code in enumerate(people, 1):
        payload, evidence = acquisition.acquire(f"senador/{code}/filiacoes.json")
        result[code] = parse_affiliations(payload, code, evidence)
        progress({"stage": "affiliations", "people": index, "total_people": len(people)})
    return result


def build_senate_history_partitions(exercises, affiliations, first_year, last_year):
    result = []
    for year in range(first_year, last_year + 1):
        rows = annual_senate_observations(exercises, affiliations, year)
        for partition in build_annual_partitions(rows, year):
            evidence = {
                item.get("sha256") or (item["url"], item.get("locator")): item
                for row in rows for item in row["evidence"]
            }
            partition["evidence"] = list(evidence.values())
            partition["aggregation_basis"] = "verified_exercises_and_affiliations_at_year_end"
            partition["reference_on"] = f"{year}-12-31"
            result.append(partition)
    return result


def publish_senate_history(
    partitions, directory, repository=None, manifest_name="senate-history-manifest.json",
):
    import json

    entries = [store_partition(directory, partition) for partition in partitions]
    if repository:
        repository.activate_partitions(partitions)
    write_atomic(directory / manifest_name, json.dumps(entries).encode())
    return entries


def associate_verified_senators(partitions, verified_identities):
    """Use prevalidated namespace bridges; names alone never create a person match."""
    associated = set()
    for partition in partitions:
        for member in partition.get("members", []):
            identity = str(member.get("person_id", ""))
            code = identity.removeprefix("senado:") if identity.startswith("senado:") else None
            if code in verified_identities:
                member["person_id"] = verified_identities[code]
                associated.add(code)
        for member in partition.get("historical_roster", []):
            code = member["source_person_id"]
            if code in verified_identities:
                member["person_id"] = verified_identities[code]
                associated.add(code)
    return len(associated)


def save_senate_history_evidence(directory, exercises, affiliations, coverage):
    save_json(directory / "historical-senate-evidence.json", {
        "schema_version": "historical_senate_evidence.v1", "exercises": exercises,
        "affiliations": affiliations, "coverage": coverage,
        "semantics": "No exercise inferred from candidacy; no undated party backfill",
    })
