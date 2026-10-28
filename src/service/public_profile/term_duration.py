"""Calendar duration until a documented mandate boundary; never infer term length."""

from calendar import monthrange
from datetime import date, timedelta


def remaining_term(ends_before, as_of):
    if type(ends_before) is not date:
        return {"status": "unknown", "years": None, "months": None, "days": None}
    months = max(0, (ends_before.year - as_of.year) * 12 + ends_before.month - as_of.month)
    anniversary_day = min(as_of.day, monthrange(ends_before.year, ends_before.month)[1])
    if ends_before.day < anniversary_day:
        months = max(0, months - 1)
    anniversary_year, month_index = divmod(as_of.year * 12 + as_of.month - 1 + months, 12)
    anniversary = date(
        anniversary_year, month_index + 1,
        min(as_of.day, monthrange(anniversary_year, month_index + 1)[1]),
    )
    return {
        "status": "documented_term_boundary",
        "years": months // 12,
        "months": months % 12,
        "days": max(0, (ends_before - anniversary).days),
        "total_days": max(0, (ends_before - as_of).days),
        "ends_before": ends_before.isoformat(),
        "last_day": (ends_before - timedelta(days=1)).isoformat(),
    }
