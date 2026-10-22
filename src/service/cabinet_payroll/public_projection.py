"""Sum decimal cost aggregates over the explicitly available monthly history."""

from collections import defaultdict
from decimal import Decimal

AMOUNTS = ("gross_amount", "allowances_amount", "total_amount")


def public_cabinet_payroll(history):
    months = [public_month(month) for month in history["months"]]
    roles = defaultdict(lambda: {key: Decimal(0) for key in AMOUNTS})
    for month in months:
        for row in month["roles"]:
            for key in AMOUNTS:
                roles[row["role"]][key] += Decimal(row[key])
    totals = [
        {"role": name, **{key: str(amount) for key, amount in amounts.items()}}
        for name, amounts in sorted(roles.items())
    ]
    return {
        "latest": months[0] if months else None,
        "months": months,
        "totals_by_role": totals,
        "truncated": history["truncated"],
        "scope": "published_staff_payroll",
        "currency": "BRL",
    }


def public_month(month):
    return {
        **{
            key: month[key]
            for key in (
                *AMOUNTS,
                "period",
                "institution",
                "currency",
                "payment_entries",
                "sourceUrl",
                "sourceObservedAt",
            )
        },
        "roles": [
            {key: row[key] for key in (*AMOUNTS, "role", "payment_entries")}
            for row in month["roles"]
        ],
    }
