"""People search for the public portal: validated query, cursor check and cached read."""

from datetime import date


def fetch_people(application, parameters):
    # Imported lazily: the public portal starts without loading the database stack.
    from database.operations import connect_database
    from database.public_people import PublicPeopleRepository
    from service.public_profile.people import search_people
    from service.public_profile.people_contracts import (
        DEFAULT_PAGE_SIZE,
        PeopleQuery,
        decode_people_cursor,
    )

    query = PeopleQuery(
        q=parameters.get("q", ""),
        uf=parameters.get("uf"),
        office_kind=parameters.get("office_kind"),
        political_party=parameters.get("political_party"),
        cursor=parameters.get("cursor"),
        limit=int(parameters.get("limit", DEFAULT_PAGE_SIZE)),
        sort=parameters.get("sort", "name"),
    )
    as_of: date = application.today()
    decode_people_cursor(query, as_of)

    def load_public_people():
        with connect_database(application.env_file) as connection:
            return search_people(PublicPeopleRepository(connection), query, as_of)

    return application.people_cache.get_or_load((query, as_of), load_public_people)
