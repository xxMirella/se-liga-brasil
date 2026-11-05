"""Political parties offered by the people search dropdown."""

import logging

from database.public_people import PublicPeopleRepository


def load_party_options(read_connections, as_of):
    """Return ((abbreviation, name), ...) for parties that have current members."""
    rows = read_connections.read(
        lambda connection: PublicPeopleRepository(connection).list_current_political_parties(
            as_of
        )
    )
    return tuple((row["abbreviation"], row["name"]) for row in rows)


def fetch_party_options(application):
    """Parties for the dropdown. A failure is not cached and yields () so the page renders."""
    as_of = application.today()
    try:
        return application.party_options_cache.get_or_load(
            as_of, lambda: load_party_options(application.read_connections, as_of)
        )
    except Exception:  # noqa: BLE001 - the dropdown is optional; search must keep working
        logging.getLogger(__name__).warning("Political party options unavailable", exc_info=True)
        return ()
