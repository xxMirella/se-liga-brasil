"""Dated official names for mutable Senate party IDs; mergers are never guessed."""

TSE_NAME_CHANGES_URL = (
    "https://www.tse.jus.br/partidos/partidos-registrados-no-tse/registrados-no-tse"
)
# Reviewed against the TSE table, "Mudanças de nome e/ou sigla", on 2026-10-23.
# Codes belong to the Senate namespace, not electoral numbers or canonical parties.
# Each cutoff is the registration decision, not an inferred date of individual affiliation.
SENATE_NAME_CHANGES = {
    "33": (("1980-01-01", "PMDB"), ("2018-05-15", "MDB")),
    "41": (("1992-01-01", "PPS"), ("2019-09-19", "CIDADANIA")),
    "578": (("1989-11-01", "PTdoB"), ("2017-09-12", "AVANTE")),
    "523": (("2006-12-19", "PR"), ("2019-02-09", "PL")),
    "521": (("2005-08-25", "PMR"), ("2009-09-21", "PRB"),
            ("2019-08-15", "REPUBLICANOS")),
    "577": (("1997-10-02", "PTN"), ("2017-05-16", "PODE")),
    "581": (("1997-08-05", "PSDC"), ("2018-05-17", "DC")),
    "579": (("2012-06-19", "PEN"), ("2018-04-26", "PATRI"),
            ("2019-03-28", "PATRIOTA")),
    "587": (("1989-02-22", "PRN"), ("2001-04-24", "PTC"), ("2022-03-31", "AGIR")),
    "588": (("1990-10-25", "PMN"), ("2023-12-05", "MOBILIZA")),
    "589": (("2015-09-29", "PMB"), ("2025-12-02", "DEMOCRATA")),
}


def historical_senate_political_party(affiliation, reference):
    code = affiliation.get("code")
    history = SENATE_NAME_CHANGES.get(code)
    if history is None:
        return affiliation.get("abbreviation"), None
    matches = [(start, name) for start, name in history if start <= reference]
    if not matches:
        return None, None
    _, name = matches[-1]
    evidence = {
        "url": TSE_NAME_CHANGES_URL,
        "locator": "Mudanças de nome e/ou sigla; Senate party code " + code,
        "reviewed_on": "2026-10-23", "source_kind": "reviewed_official_table",
    }
    return name, evidence
