"""The 13 database reads of a person profile, behind one interface with three implementations.

`LiveProfileSource` runs them against PostgreSQL (the current path). `RecordingProfileSource`
wraps another source and keeps what each read returned (used by the snapshot build).
`StoredProfileSource` replays those results without touching the database; only the proposition
pages the snapshot does not hold are still read live.
"""

from contextlib import nullcontext
from copy import deepcopy

PROPOSITIONS = "propositions"
STORED_PROPOSITION_PAGE = 1
# Repository-shaped reads (names are those of PublicPeopleRepository / PublicAssetsRepository)
# plus the five function-shaped reads of the profile.
READ_NAMES = (
    "fetch_public_person",
    "fetch_current_exercises",
    "fetch_public_affiliations",
    "fetch_latest_public_payments",
    "fetch_person",
    "fetch_asset_years",
    "fetch_asset_items",
    "historical_activity",
    "attendance",
    PROPOSITIONS,
    "attendance_history",
    "legal_scopes",
    "payroll_history",
)


class LiveProfileSource:
    def __init__(self, connection):
        from database.public_assets import PublicAssetsRepository
        from database.public_people import PublicPeopleRepository

        self.connection = connection
        self._people = PublicPeopleRepository(connection)
        self._assets = PublicAssetsRepository(connection)

    def read_snapshot(self):
        return self._people.read_snapshot()

    def fetch_public_person(self, person_id):
        return self._people.fetch_public_person(person_id)

    def fetch_current_exercises(self, person_id, as_of):
        return self._people.fetch_current_exercises(person_id, as_of)

    def fetch_public_affiliations(self, person_id, as_of):
        return self._people.fetch_public_affiliations(person_id, as_of)

    def fetch_latest_public_payments(self, person_id, as_of):
        return self._people.fetch_latest_public_payments(person_id, as_of)

    def fetch_person(self, person_id):
        return self._people.fetch_person(person_id)

    def fetch_asset_years(self, person_id, as_of):
        return self._assets.fetch_asset_years(person_id, as_of)

    def fetch_asset_items(self, person_id, years):
        return self._assets.fetch_asset_items(person_id, years)

    def historical_activity(self, person_id, as_of):
        from database.alerj_history import fetch_person_historical_activity

        return fetch_person_historical_activity(self.connection, person_id, as_of)

    def attendance(self, person_id, as_of):
        from database.attendance import fetch_person_attendance

        return fetch_person_attendance(self.connection, person_id, as_of)

    def propositions(self, person_id, as_of, page):
        from database.public_propositions import fetch_person_propositions

        return fetch_person_propositions(self.connection, person_id, as_of, page)

    def attendance_history(self, person_id, as_of):
        from database.attendance import fetch_person_attendance_history

        return fetch_person_attendance_history(self.connection, person_id, as_of)

    def legal_scopes(self, person_id, as_of):
        from database.office_legal_scopes import fetch_public_office_scopes

        return fetch_public_office_scopes(self.connection, person_id, as_of)

    def payroll_history(self, person_id, as_of):
        from database.cabinet_payroll import fetch_cabinet_payroll_history

        return fetch_cabinet_payroll_history(self.connection, person_id, as_of)


class RecordingProfileSource:
    """Delegates to `inner` and records each read's result in `recorded` (one entry per read)."""

    def __init__(self, inner):
        self._inner = inner
        self.recorded: dict = {}

    def read_snapshot(self):
        return self._inner.read_snapshot()

    def __getattr__(self, name):
        if name not in READ_NAMES:
            raise AttributeError(name)
        read = getattr(self._inner, name)

        def recording_read(*arguments):
            result = read(*arguments)
            if name != PROPOSITIONS or arguments[-1] == STORED_PROPOSITION_PAGE:
                self.recorded[name] = deepcopy(result)
            return result

        return recording_read


class StoredProfileSource:
    """Replays recorded reads. `live` serves what is not stored (other proposition pages)."""

    def __init__(self, recorded: dict, live):
        self._recorded = recorded
        self._live = live

    def read_snapshot(self):
        return nullcontext()

    def __getattr__(self, name):
        if name not in READ_NAMES:
            raise AttributeError(name)
        if name == PROPOSITIONS:
            return self._propositions

        def stored_read(*_arguments):
            return self._recorded[name]

        return stored_read

    def _propositions(self, person_id, as_of, page):
        if page == STORED_PROPOSITION_PAGE and PROPOSITIONS in self._recorded:
            return self._recorded[PROPOSITIONS]
        return self._live.propositions(person_id, as_of, page)
