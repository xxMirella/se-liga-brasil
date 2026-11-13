"""Load a person profile in one read snapshot over a pooled connection.

The profile is composed from 13 reads (the plan card P1-C speaks of 14: it also counts the
`read_snapshot` transaction, which is not a read of rows and is not stored).
When a fresh `person_profile_snapshot` row exists the reads are replayed from it
(3 statements instead of 13); any miss or failure falls back to the database, with the same
composition and therefore the same result.
"""

import logging

logger = logging.getLogger(__name__)


def compose_profile(source, person_id, as_of, proposal_page=1):
    """The profile dict, from any source of the 13 reads (live, recording or stored)."""
    from service.cabinet_payroll.public_projection import public_cabinet_payroll
    from service.public_profile.assets import get_public_assets
    from service.public_profile.people import get_public_person

    with source.read_snapshot():
        profile = get_public_person(source, person_id, as_of)
        profile["assets"] = get_public_assets(source, person_id, as_of)
        profile["historical_activity"] = source.historical_activity(person_id, as_of)
        profile["attendance"] = source.attendance(person_id, as_of)
        profile["propositions"] = source.propositions(person_id, as_of, proposal_page)
        profile["attendance_history"] = source.attendance_history(person_id, as_of)
        profile["legal_scopes"] = source.legal_scopes(person_id, as_of)
        profile["cabinet_payroll"] = public_cabinet_payroll(
            source.payroll_history(person_id, as_of)
        )
    return profile


def load_person_profile(read_connections, person_id, as_of, proposal_page=1):
    from application.person_profile_reads import LiveProfileSource, StoredProfileSource
    from database.public_people import PublicPeopleRepository
    from service.serving.person_profile_snapshot import read_stored_reads

    def read_profile(connection):
        # One snapshot for the whole profile: inner read_snapshot calls join it.
        with PublicPeopleRepository(connection).read_snapshot():
            live = LiveProfileSource(connection)
            stored = read_stored_reads(connection, person_id, as_of)
            if stored is not None:
                try:
                    return compose_profile(
                        StoredProfileSource(stored, live), person_id, as_of, proposal_page
                    )
                except Exception:
                    logger.exception("person profile snapshot unusable; reading live")
            return compose_profile(live, person_id, as_of, proposal_page)

    # Pooled read connection (transaction pooler, port 6543): returned to the pool on
    # success, discarded on error; the snapshot keeps its SET LOCAL 5s statement timeout.
    return read_connections.read(read_profile)
