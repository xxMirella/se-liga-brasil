"""Votes and voting history of a person, read through the response cache."""

from service.public_profile import PublicProfileError


def fetch_votes(application, person_id, parameters):
    if parameters.get("scope", "period") not in {"history", "period"}:
        raise PublicProfileError("INVALID_TIMELINE_SCOPE")
    history = parameters.get("scope") == "history"
    return application.votes_cache.get_or_load(
        person_id,
        parameters,
        application.today(),
        lambda: load_votes(application, person_id, parameters),
        warm_catalog=history,
        dataset_reader=application.dataset_reader,
    )


def load_votes(application, person_id, parameters):
    from application.public_api import build_vote_query
    from database.operations import connect_database
    from database.public_profile import PublicProfileRepository
    from service.public_profile.storage_votes import get_person_storage_votes

    if parameters.get("scope") == "history":
        return fetch_history(application, person_id, parameters)
    parameters = {key: value for key, value in parameters.items() if key != "scope"}
    query = build_vote_query(person_id, parameters)
    with connect_database(application.env_file) as connection:
        return get_person_storage_votes(
            PublicProfileRepository(connection), application.dataset_reader, query
        )


def fetch_history(application, person_id, parameters):
    from database.operations import connect_database
    from database.public_profile import PublicProfileRepository
    from service.public_profile.storage_history import get_person_storage_history

    with connect_database(application.env_file) as connection:
        return get_person_storage_history(
            PublicProfileRepository(connection),
            application.dataset_reader,
            person_id,
            office_kind=parameters.get("office_kind"),
            exercise_id=int(parameters["exercise_id"]) if parameters.get("exercise_id") else None,
            cursor=parameters.get("cursor"),
            limit=int(parameters.get("limit", "30")),
            as_of=application.today(),
        )
