"""Fictional panorama used by the opening/timeline tests (no real data)."""

from datetime import date

from service.majority_panorama.contracts import (
    HouseComposition,
    Legislature,
    MajorityPanorama,
    PresidentialTerm,
)


def house(name, total, **seats):
    return HouseComposition(name, total, seats, {}, 2020)


def legislature(first_year, camara=None, senado=None):
    end = first_year + 4
    return Legislature(str(first_year), first_year, end, f"{first_year}–{end - 1}", camara, senado)


def term(short, bloc_key, start_year, end_year):
    return PresidentialTerm(
        f"{short} Fictício", short, "PXX", bloc_key, date(start_year, 1, 1),
        date(end_year, 1, 1), f"{start_year}–{end_year - 1}",
    )


def fictional_panorama():
    return MajorityPanorama(
        legislatures=(
            legislature(2015),
            legislature(2019, house("camara", 100, left=20, center=30, right=45, unaffiliated=5),
                        house("senado", 10, left=2, center=3, right=5)),
            legislature(2023, house("camara", 100, left=60, center=10, right=20, far_right=10),
                        house("senado", 10, left=6, center=1, right=3)),
        ),
        presidents=(term("Alfa", "center", 2015, 2019), term("Beta", "right", 2019, 2023),
                    term("Gama", "left", 2023, 2027)),
        generated_on=date(2026, 11, 1),
    )
