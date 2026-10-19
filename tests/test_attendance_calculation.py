from decimal import Decimal

import pytest

from service.attendance.calculation import AttendanceCounts, calculate_attendance


def test_excused_absences_are_visible_not_turned_into_presence():
    counts = AttendanceCounts(required=10, present=8, excused_absences=1, unexcused_absences=1)
    assert calculate_attendance(counts, coverage_complete=True) == Decimal("80.0")


@pytest.mark.parametrize(
    ("counts", "complete"),
    [
        (AttendanceCounts(0, 0, 0, 0), True),
        (AttendanceCounts(10, 8, 0, 1, 1), True),
        (AttendanceCounts(10, 8, 1, 1), False),
    ],
)
def test_missing_obligations_never_produce_a_percentage(counts, complete):
    assert calculate_attendance(counts, coverage_complete=complete) is None


@pytest.mark.parametrize("values", [(10, 11, 0, 0), (-1, 0, 0, 0), (True, 1, 0, 0)])
def test_inconsistent_counts_are_rejected(values):
    with pytest.raises(ValueError):
        AttendanceCounts(*values)
