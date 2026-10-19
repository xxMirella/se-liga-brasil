"""Calculate attendance without inventing schedules or treating unknown days as absences."""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal


@dataclass(frozen=True)
class AttendanceCounts:
    required: int
    present: int
    excused_absences: int
    unexcused_absences: int
    unknown: int = 0

    def __post_init__(self):
        counts = (
            self.required, self.present, self.excused_absences,
            self.unexcused_absences, self.unknown,
        )
        if any(type(value) is not int or value < 0 for value in counts):
            raise ValueError("Attendance counts must be nonnegative integers")
        if sum(counts[1:]) != self.required:
            raise ValueError("Attendance outcomes must account for every required unit")


def calculate_attendance(counts: AttendanceCounts, *, coverage_complete: bool):
    """Return physical/recorded attendance, not a legal compliance determination.

    Excused absences stay visible and in the denominator. An institution-specific
    legal indicator may treat them differently and must be named separately.
    """
    if not coverage_complete or counts.unknown or not counts.required:
        return None
    percentage = Decimal(counts.present) * 100 / Decimal(counts.required)
    return percentage.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
