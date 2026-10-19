"""Calendar partitions with explicit exclusive ends, independent from acquisition."""

from calendar import monthrange
from datetime import timedelta


def month_intervals(starts_on, ends_before):
    if starts_on >= ends_before:
        raise ValueError("Expected nonempty interval with an exclusive end")
    while starts_on < ends_before:
        last_day = starts_on.replace(day=monthrange(starts_on.year, starts_on.month)[1])
        upper = ends_before if ends_before <= last_day else last_day + timedelta(days=1)
        yield starts_on, upper
        starts_on = upper
