"""Brazilian date and money formats used by the profile identity and summary."""

from decimal import Decimal, InvalidOperation

MONTH_ABBREVIATIONS = (
    "jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez",
)


def split_iso_date(value):
    """Return (year, month, day) from an ISO date or year-month prefix; None when malformed."""
    parts = str(value or "").split("-")
    try:
        numbers = [int(part) for part in parts[:3]]
    except ValueError:
        return None
    if len(numbers) < 2 or not 1 <= numbers[1] <= 12:
        return None
    return (numbers + [None])[:3] if len(numbers) == 2 else numbers


def format_month_year(value):
    """'2023-02-01' or '2023-02' becomes 'fev/2023'; None when it cannot be read."""
    parsed = split_iso_date(value)
    return f"{MONTH_ABBREVIATIONS[parsed[1] - 1]}/{parsed[0]}" if parsed else None


def format_full_date(value):
    """'2027-01-31' becomes '31/01/2027'; None when it is not a complete date."""
    parsed = split_iso_date(value)
    if not parsed or parsed[2] is None:
        return None
    return f"{parsed[2]:02d}/{parsed[1]:02d}/{parsed[0]}"


def format_reais(value):
    """'46366.19' becomes 'R$ 46.366,19'; None when the amount is not a finite number."""
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or abs(amount) >= Decimal("1e21"):
            return None
        grouped = format(amount, ",.2f")
    except (InvalidOperation, ValueError):
        return None
    return "R$ " + grouped.translate(str.maketrans({",": ".", ".": ","}))
