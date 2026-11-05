"""Fictional chambers with and without party detail, for the period section tests."""

from datetime import date

from service.majority_panorama.contracts import (
    HouseComposition,
    Legislature,
    MajorityPanorama,
    PartyCount,
    PresidentialTerm,
)


def _parties(*pairs):
    return tuple(PartyCount(name, count) for name, count in pairs)


def camara_with_parties():
    return HouseComposition(
        "camara", 513,
        {"left": 100, "center": 150, "right": 200, "far_right": 40, "undetermined": 20,
         "unaffiliated": 3},
        {"left": _parties(("PAA", 60), ("PAB", 40)), "center": _parties(("PBA", 100), ("PBB", 50)),
         "right": _parties(("PCA", 120), ("PCB", 50), ("PCC", 30)),
         "far_right": _parties(("PDA", 40)), "undetermined": _parties(("PEA", 20))},
        2026, date(2026, 10, 29), notes=("Nota fictícia de cobertura.",),
    )


def senado_with_parties():
    return HouseComposition(
        "senado", 81, {"left": 20, "center": 21, "right": 40},
        {"left": _parties(("PAA", 20)), "center": _parties(("PBA", 21)),
         "right": _parties(("PCA", 40))}, 2026,
    )


def camara_without_parties():
    return HouseComposition("camara", 513, {"left": 150, "center": 150, "right": 213}, {}, 2018)


def senado_without_parties():
    return HouseComposition("senado", 81, {"left": 30, "center": 30, "right": 21}, {}, 2018)


def period_panorama():
    return MajorityPanorama(
        legislatures=(
            Legislature("2015", 2015, 2019, "2015–2018", None, None),
            Legislature("2019", 2019, 2023, "2019–2022", camara_without_parties(),
                        senado_without_parties()),
            Legislature("2023", 2023, 2027, "2023–2026", camara_with_parties(),
                        senado_with_parties()),
        ),
        presidents=(
            PresidentialTerm("Ana Fictícia", "Ana", "PXX", "center", date(2015, 1, 1),
                             date(2019, 1, 1), "2015–2018"),
            PresidentialTerm("Bia Fictícia", "Bia", "PXY / PXZ", "right", date(2019, 1, 1),
                             date(2023, 1, 1), "2019–2022"),
            PresidentialTerm("Caio Fictício", "Caio", "sem partido", "unaffiliated",
                             date(2023, 1, 1), date(2027, 1, 1), "2023–2026"),
        ),
        generated_on=date(2026, 11, 1),
        sources_note="Fonte fictícia observada em 29/10/2026.",
        coverage_notes=("Cobertura fictícia parcial.",),
    )
