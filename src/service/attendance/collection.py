"""Resumable, bounded attendance backfill using verified canonical identities."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from crawlers.camara.attendance import collect_attendance_history
from crawlers.camara.voting_identity import cached_profile_artifact, resolve_voting_people
from service.observability.reporting import describe_error
from storage.files import load_json, save_json


def discover_attendance_members(acquisition):
    members = {}
    for legislature in range(51, 58):
        query = f"deputados?idLegislatura={legislature}&itens=100"
        for rows, _ in acquisition.pages(query, "camara_historical_roster"):
            index_attendance_members(members, rows, legislature)
    return members


def index_attendance_members(members, rows, legislature):
    first_year = max(2000, 1999 + 4 * (legislature - 51))
    for row in rows:
        members.setdefault(str(row["id"]), row | {"attendance_start_year": first_year})


def collect_attendance_batch(repository, acquisition, *, limit=25, person_id=None, years=None):
    if not 1 <= limit <= 100:
        raise ValueError("Attendance batch must contain 1 to 100 profiles")
    scope = "progress" if years is None else "years-" + "-".join(map(str, sorted(set(years))))
    checkpoint = acquisition.configuration.storage_directory / "attendance" / f"{scope}.json"
    state = load_json(checkpoint) or {}
    members = discover_attendance_members(acquisition)
    artifacts = prepare_attendance_profiles(
        acquisition, members, state, limit, connection=repository.connection, person_id=person_id
    )
    verified = resolve_voting_people(repository.connection, artifacts)
    completed, failures = [], []
    for key in artifacts:
        match = verified.get(key)
        if person_id and (not match or match["person_id"] != person_id):
            continue
        if not match:
            state[key] = {"checked_at": datetime.now().astimezone().isoformat(),
                          "status": "identity_not_in_scope"}
            continue
        try:
            result = collect_attendance_history(
                acquisition, repository, members[key], match["person_id"], years=years
            )
        except Exception as error:
            failures.append({"person_id": match["person_id"], **describe_error(error)})
            break
        state[key] = {"checked_at": datetime.now().astimezone().isoformat(),
                      "person_id": match["person_id"], "result": result}
        completed.append({"person_id": match["person_id"], **result})
        failures.extend(result.get("failures", []))
        save_json(checkpoint, state)
    save_json(checkpoint, state)
    return {"people": completed, "profiles_inspected": len(artifacts), "failures": failures,
            "source_members": len(members), "status": "partial",
            "coverage": "camara_only_other_institutions_pending"}


def prepare_attendance_profiles(
    acquisition, members, state, limit, *, connection=None, person_id=None,
):
    available = {
        key: cached_profile_artifact(acquisition.configuration, key)
        for key in members if not attendance_recently_checked(state.get(key))
    }
    known = resolve_voting_people(
        connection, {key: artifact for key, artifact in available.items() if artifact is not None}
    ) if connection is not None else {}
    if person_id:
        available = {
            key: artifact for key, artifact in available.items()
            if known.get(key, {}).get("person_id") == person_id
        }
    keys = sorted(
        available, key=lambda key: (key not in known, available[key] is None, int(key))
    )[:limit]
    artifacts = {}
    for key in keys:
        artifact = available[key]
        if artifact is None:
            _, artifact = acquisition.json_document(f"deputados/{key}", "camara_profile")
        artifacts[key] = artifact
    return artifacts


def attendance_recently_checked(receipt):
    if not receipt or receipt.get("result", {}).get("failures"):
        return False
    checked = datetime.fromisoformat(receipt["checked_at"])
    return checked > datetime.now(ZoneInfo("America/Belem")) - timedelta(hours=24)
