"""The crawler discovers facts; consolidation is gated by new validated content."""

from pathlib import Path
from tempfile import TemporaryDirectory

from service.voting_pipeline.consolidation import consolidate_acquisition


def collect_source_input(
    connection,
    storage,
    source,
    start,
    end,
    output_path,
    *,
    limit=25,
    max_identity_profiles=10,
    proposition_ids=(),
    cached_only=False,
):
    if source == "senado":
        from service.voting_pipeline.source_senado import collect_senate_source_files

        return collect_senate_source_files(
            connection,
            storage,
            start,
            end,
            output_path,
            max_partitions=3,
            max_votings=limit,
            max_processes=min(limit, 100),
            max_identity_profile_downloads=max_identity_profiles,
            **({"cached_only": True} if cached_only else {}),
        )
    if source == "camara":
        if cached_only:
            raise ValueError("Cached source replay currently supports Senate voting")
        from crawlers.camara.voting_pipeline import collect_camara_source_files

        return collect_camara_source_files(
            connection,
            storage,
            start,
            end,
            output_path,
            max_votings=limit,
            max_propositions=min(limit, 100),
            max_identity_profile_downloads=max_identity_profiles,
            max_vote_rows=100000,
            **({"proposition_ids": proposition_ids} if proposition_ids else {}),
        )
    raise ValueError("Unsupported voting source")


def run_source_refresh(
    connection,
    storage,
    repository,
    source,
    start,
    end,
    *,
    publisher=None,
    limit=25,
    max_identity_profiles=10,
    proposition_ids=(),
    cached_only=False,
):
    if source not in {"camara", "senado"} or start > end or (end - start).days > 62:
        raise ValueError("Select a supported source and bounded voting interval")
    lock_key = "se_liga_brasil:voting-dataset:" + source
    acquired = connection.execute(
        "SELECT pg_try_advisory_lock(hashtext(%s)) AS acquired", (lock_key,)
    ).fetchone()["acquired"]
    if not acquired:
        raise ValueError("Voting dataset source is already running")
    try:
        storage, repository = Path(storage), Path(repository)
        storage.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=storage, prefix="daily-voting-") as temporary:
            temporary = Path(temporary)
            result = collect_source_input(
                connection,
                storage,
                source,
                start,
                end,
                temporary / "input.ndjson",
                limit=limit,
                max_identity_profiles=max_identity_profiles,
                **({"proposition_ids": proposition_ids} if proposition_ids else {}),
                **({"cached_only": True} if cached_only else {}),
            )
            daily = consolidate_acquisition(
                result, source, start, end, repository, temporary, publisher
            )
            return daily | {
                "source": source,
                "acquired_rows": result["rows"],
                "identity_unresolved": result.get("identity_unresolved", 0),
                "description_missing": result.get("description_missing", 0),
                "discovery_complete": result.get("discovery_complete", True),
                "coverage": "requested_source_interval_not_full_career",
            }
    finally:
        connection.execute("SELECT pg_advisory_unlock(hashtext(%s))", (lock_key,))
