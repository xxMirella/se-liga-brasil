"""Public read filters with stable, non-sensitive errors."""

from dataclasses import dataclass
from datetime import date
from uuid import UUID

OFFICE_KINDS = {
    "federal_deputy",
    "state_deputy",
    "district_deputy",
    "senator",
    "councillor",
    "mayor",
    "other",
}


class PublicProfileError(ValueError):
    def __init__(self, code, status_code=400):
        self.code = code
        self.status_code = status_code
        super().__init__(code)


@dataclass(frozen=True)
class VoteQuery:
    person_id: str
    start_on: date
    end_on: date
    office_kind: str | None = None
    exercise_id: int | None = None
    cursor: str | None = None
    limit: int = 30

    def __post_init__(self):
        try:
            canonical_id = str(UUID(self.person_id))
        except (ValueError, TypeError, AttributeError) as error:
            raise PublicProfileError("INVALID_PERSON_ID") from error
        object.__setattr__(self, "person_id", canonical_id)
        if type(self.start_on) is not date or type(self.end_on) is not date:
            raise PublicProfileError("INVALID_PERIOD")
        if self.start_on > self.end_on:
            raise PublicProfileError("INVALID_PERIOD")
        if type(self.limit) is not int or not 1 <= self.limit <= 100:
            raise PublicProfileError("INVALID_PAGE_SIZE")
        if self.office_kind is not None and (
            not isinstance(self.office_kind, str) or self.office_kind not in OFFICE_KINDS
        ):
            raise PublicProfileError("INVALID_OFFICE_KIND")
        if self.exercise_id is not None and (
            type(self.exercise_id) is not int or not 1 <= self.exercise_id <= 2**63 - 1
        ):
            raise PublicProfileError("INVALID_EXERCISE_ID")
