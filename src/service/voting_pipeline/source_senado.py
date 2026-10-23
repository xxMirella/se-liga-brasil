"""Senate originals to bounded private daily inputs; no SQL votes are inserted."""

import json
from datetime import datetime
from itertools import islice
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import urlencode

from crawlers.senado.acquisition import SenateAcquisition
from crawlers.senado.configuration import OFFICIAL_HOSTS, SOURCE, SenateConfiguration
from crawlers.senado.legislative import collect_process_details
from crawlers.senado.legislative_voting import normalize_voting_record, resolve_voting_individuals
from crawlers.senado.voting_identity import cached_identity_profiles, resolve_profile_identities
from crawlers.senado.voting_pipeline import monthly_partitions, select_unique_votings
from crawlers.senado.voting_profile_acquisition import (
    IdentityProfileAcquisition,
    validate_identity_profile_budget,
)
from service.ingestion.contracts import IngestionError
from service.voting_pipeline.runtime import cached_source_acquisition, official_source_acquisition
from storage.files import (
    create_private_directory,
    hash_content,
    hash_file,
    load_json,
    save_json,
    write_json_line,
)

PARSER_VERSION = "senado-daily-voting-input-v3"
MAX_INPUT_BYTES = 64 * 1024 * 1024
MAX_INPUT_ROWS = 100000


def collect_senate_source_files(
    connection,
    storage,
    start,
    end,
    output_path,
    *,
    max_partitions=1,
    max_votings=1000,
    max_processes=25,
    max_identity_profile_downloads=0,
    cached_only=False,
):
    partitions = monthly_partitions(start, end, max_partitions)
    validate_identity_profile_budget(max_identity_profile_downloads)
    if cached_only and max_identity_profile_downloads:
        raise IngestionError("OFFLINE_VOTING_CANNOT_DOWNLOAD_IDENTITY_PROFILES")
    if not 1 <= max_votings <= 10000 or not 0 <= max_processes <= 100:
        raise IngestionError("INVALID_SENATE_ANALYTICAL_BUDGET")
    configuration = SenateConfiguration(Path(storage).resolve())
    profiles = cached_identity_profiles(configuration.storage_directory)
    identities = resolve_profile_identities(connection, profiles)
    profile_acquisition = IdentityProfileAcquisition(max_identity_profile_downloads)
    profile_acquisition.mark_cached_profiles(profiles, configuration)
    context = senate_acquisition_context(connection, configuration, cached_only)
    with context as acquisition:
        return normalize_senate_source_files(
            connection,
            acquisition,
            partitions,
            output_path,
            identities,
            profile_acquisition,
            max_votings=max_votings,
            max_processes=0 if cached_only else max_processes,
            identity_observations={item.sha256: item.fetched_at for item in profiles},
        )


def senate_acquisition_context(connection, configuration, cached_only):
    if cached_only:
        from crawlers.senado.cached_acquisition import CachedSenateAcquisition

        return cached_source_acquisition(connection, configuration, SOURCE, CachedSenateAcquisition)
    return official_source_acquisition(
        connection, configuration, SOURCE, OFFICIAL_HOSTS, SenateAcquisition
    )


def normalize_senate_source_files(
    connection,
    acquisition,
    partitions,
    output_path,
    identities,
    profile_acquisition,
    *,
    max_votings=1000,
    max_processes=25,
    identity_observations=None,
):
    """Injectable source adapter; input periods were bounded before acquisition."""
    rows, receipts, processes, seen = [], [], {}, {}
    unresolved = descriptions_missing = input_bytes = 0
    evidence_dependencies, secret_keys = set(), set()
    secret_votings = []
    identity_observations = dict(identity_observations or {})
    for start, end in partitions:
        query = urlencode({"dataInicio": start.isoformat(), "dataFim": end.isoformat(), "v": 2})
        payload, artifact = acquisition.json_document("votacao.json?" + query, "senado_votings")
        selected = select_unique_votings(payload, seen, start, end, max_votings)
        profile_acquisition.extend_resolved_index(connection, acquisition, selected, identities)
        update_identity_observations(acquisition, identities, identity_observations)
        secret_keys.update(
            "senado:" + normalize_voting_record(row)["source_key"]
            for row in selected
            if row["votacaoSecreta"] == "S"
        )
        secret_votings.extend(secret_voting_observations(selected, artifact))
        votes, missing = resolve_voting_individuals(selected, identities)
        unresolved += missing
        enrich_processes(acquisition, selected, processes, max_processes)
        indexed = {normalize_voting_record(row)["source_key"]: row for row in selected}
        for vote in votes:
            record = daily_vote_record(
                indexed[vote["voting_key"]], vote, artifact, processes, identity_observations
            )
            descriptions_missing += record["description"] is None
            input_bytes += len(json.dumps(record, ensure_ascii=False).encode("utf-8")) + 1
            if input_bytes > MAX_INPUT_BYTES or len(rows) >= MAX_INPUT_ROWS:
                raise IngestionError("SENATE_ANALYTICAL_INPUT_LIMIT_EXCEEDED")
            evidence_dependencies.add(vote["identity_profile_sha256"])
            rows.append(record)
        receipts.append(partition_receipt(start, end, artifact, len(selected), len(votes), missing))
    evidence_dependencies.update(value[1] for value in processes.values())
    result = write_daily_input(
        output_path, rows, receipts, evidence_dependencies, secret_keys, secret_votings
    )
    return (
        result
        | profile_acquisition.summary()
        | {
            "identity_unresolved": unresolved,
            "description_missing": descriptions_missing,
            "processes_acquired": len(processes),
            "status": "partial",
        }
    )


def enrich_processes(acquisition, selected, processes, maximum):
    remaining = maximum - len(processes)
    if remaining <= 0:
        return
    keys = dict.fromkeys(str(row["idProcesso"]) for row in selected)
    needed = list(islice((key for key in keys if key not in processes), remaining))
    if needed:
        for process, artifact in collect_process_details(
            acquisition, needed, max_processes=maximum
        ):
            processes[process["source_key"]] = (process, artifact.sha256, artifact.fetched_at)


def daily_vote_record(raw, vote, artifact, processes, identity_observations=None):
    voting = normalize_voting_record(raw)
    process, _, process_observed_at = processes.get(str(raw["idProcesso"]), ({}, None, None))
    profile_observed_at = (identity_observations or {}).get(vote["identity_profile_sha256"])
    description = nullable_text(process.get("description") or raw.get("ementa"))
    return {
        "person_id": vote["person_id"],
        "voting_id": "senado:" + vote["voting_key"],
        "institution_code": "senado",
        "occurred_on": voting["occurred_on"],
        "date_precision": "day",
        "vote_choice": vote["choice"],
        "participation_status": vote["participation_status"],
        "evidence_sha256": artifact.sha256,
        "validation_status": "verified",
        "matter_kind": nullable_text(process.get("kind") or raw.get("sigla")),
        "matter_number": nullable_text(process.get("number") or raw.get("numero")),
        "matter_year": optional_year(process.get("year") or raw.get("ano")),
        "matter_name": nullable_text(raw.get("identificacao")),
        "description": description,
        "description_origin": "official_text" if description else "unknown",
        "official_url": nominal_voting_url(raw),
        "voting_subject": nullable_text(raw.get("descricaoVotacao")),
        "round_number": voting["round_number"],
        "source_observed_at": latest_observation(
            artifact.fetched_at, process_observed_at, profile_observed_at
        ),
    }


def nominal_voting_url(raw):
    """The legacy matter code identifies the readable nominal lists, unlike process IDs."""
    matter_code = str(raw.get("codigoMateria", ""))
    if not matter_code.isascii() or not matter_code.isdecimal() or int(matter_code) <= 0:
        return None
    return (
        "https://www25.senado.leg.br/web/atividade/materias/-/materia/" + matter_code + "/votacoes"
    )


def latest_observation(*timestamps):
    observations = [datetime.fromisoformat(value) for value in timestamps if value]
    if any(value.tzinfo is None for value in observations):
        raise IngestionError("SENATE_OBSERVATION_TIMEZONE_REQUIRED")
    return max(observations).isoformat()


def update_identity_observations(acquisition, identities, observations):
    configuration = getattr(acquisition, "configuration", None)
    if configuration is None:
        return
    for key, (_, digest) in identities.items():
        if digest in observations:
            continue
        url = f"https://legis.senado.leg.br/dadosabertos/senador/{key}.json"
        resource_key = "senado-" + hash_content(url)
        manifest = load_json(
            configuration.storage_directory / "manifests" / (resource_key + ".json"), {}
        )
        if manifest.get("sha256") == digest:
            observations[digest] = manifest["fetched_at"]


def nullable_text(value):
    return str(value).strip() if value is not None and str(value).strip() else None


def optional_year(value):
    if value is None:
        return None
    try:
        result = int(value)
    except (ValueError, TypeError) as error:
        raise IngestionError("INVALID_SENATE_MATTER_YEAR") from error
    if not 1800 <= result <= 2200:
        raise IngestionError("INVALID_SENATE_MATTER_YEAR")
    return result


def partition_receipt(start, end, artifact, votings, votes, missing):
    return {
        "source": "senado",
        "channel": "plenary",
        "starts_on": start.isoformat(),
        "ends_on": end.isoformat(),
        "artifact_sha256": artifact.sha256,
        "source_observed_at": artifact.fetched_at,
        "parser_version": PARSER_VERSION,
        "votings": votings,
        "resolved_votes": votes,
        "unresolved_votes": missing,
        "collection_complete": False,
        "coverage": "requested_period_not_entire_career",
    }


def secret_voting_observations(rows, artifact):
    observations = []
    for row in rows:
        if row["votacaoSecreta"] != "S":
            continue
        voting = normalize_voting_record(row)
        observations.append(
            {
                "voting_id": "senado:" + voting["source_key"],
                "occurred_on": voting["occurred_on"],
                "source_observed_at": artifact.fetched_at,
            }
        )
    return observations


def write_daily_input(
    output_path, rows, receipts, evidence_dependencies=(), secret_keys=(), secret_votings=()
):
    path = Path(output_path)
    create_private_directory(path.parent)
    temporary_path = None
    try:
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False
        ) as output:
            temporary_path = Path(output.name)
            temporary_path.chmod(0o600)
            for row in rows:
                write_json_line(output, row)
        temporary_path.replace(path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    metadata = {
        "parser_version": PARSER_VERSION,
        "input_sha256": hash_file(path),
        "evidence_dependencies": sorted(evidence_dependencies),
        "explicit_secret_voting_keys": sorted(secret_keys),
        "explicit_secret_votings": sorted(secret_votings, key=lambda item: item["voting_id"]),
        "rows": len(rows),
        "receipts": receipts,
        "collection_complete": False,
    }
    save_json(path.with_suffix(path.suffix + ".manifest.json"), metadata)
    return metadata | {"input_path": str(path)}
