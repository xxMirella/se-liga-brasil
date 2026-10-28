"""Reviewed source passages defining exercise boundaries independently of election dates."""

from crawlers.state_government.parsing import evidence, source_exercise
from service.state_government_history.document_text import document_text
from service.state_government_history.provenance import documented_exercise

# Closed periods use explicit succession evidence, never expected electoral term ends.
DAY_PERIODS = (
    ("franca", "Márcio França", "SP", "2018-04-06", "2019-01-01", "Márcio França assume o cargo"),
    ("doria", "João Doria", "SP", "2019-01-01", "2022-03-31", "O governador João Doria (PSDB)"),
    (
        "garcia",
        "Rodrigo Garcia",
        "SP",
        "2022-03-31",
        "2023-01-01",
        "Aos trinta e um dias do mês de março de dois mil e vinte e dois",
    ),
    (
        "freitas",
        "Tarcísio Gomes de Freitas",
        "SP",
        "2023-01-01",
        None,
        "tomaram posse como governador e vice-governador",
    ),
    ("castro_2021", "Cláudio Castro", "RJ", "2021-05-01", "2023-01-01", "01-05-2021"),
    (
        "castro_2023",
        "Cláudio Castro",
        "RJ",
        "2023-01-01",
        "2026-03-23",
        "tomou posse de seu segundo mandato",
    ),
    (
        "castro_end",
        "Ricardo Couto",
        "RJ",
        "2026-03-23",
        None,
        "quem assume interinamente o governo do estado é o desembargador Ricardo Couto",
    ),
)


def verified_periods(artifacts):
    records = [
        documented_exercise(
            artifacts[key],
            name,
            uf,
            start,
            end,
            quote,
            document_text(artifacts[key]),
        )
        for key, name, uf, start, end, quote in DAY_PERIODS
    ]
    append_boundary_evidence(records, artifacts)
    records.extend(ipea_annual_periods(artifacts["ipea"]))
    records.extend(accounting_periods(artifacts))
    return records


def append_boundary_evidence(records, artifacts):
    boundaries = {
        "Márcio França": "doria",
        "João Doria": "garcia",
        "Rodrigo Garcia": "freitas",
        "Cláudio Castro": "castro_end",
    }
    for row in records:
        key = boundaries.get(row["name"])
        if key:
            row["evidence"].append(evidence(artifacts[key], "Documented succession/renunciation"))
        if row["name"] == "Rodrigo Garcia":
            row["source_discrepancies"] = [
                "Heading lists 01/04/2022; signed accession term explicitly dates 31/03/2022 18h."
            ]


def ipea_annual_periods(artifact):
    text = " ".join(document_text(artifact).split())
    periods = (("Rosinha Garotinho", 2003, 2006),)
    result = []
    for name, first, last in periods:
        quote = f"{name} {first}-{last}"
        if quote not in text:
            raise ValueError("STATE_GOVERNMENT_IPEA_PERIOD_NOT_FOUND")
        row = source_exercise(name, "RJ", name)
        row.update(
            year_start=first,
            year_end=last,
            date_precision="year",
            source_url=artifact.resource.url,
            evidence=[
                evidence(artifact, "p.19 Governadores do Estado do Rio de Janeiro: " + quote)
            ],
        )
        result.append(row)
    return result


def enrich_alckmin_membership(records, artifact):
    text = " ".join(document_text(artifact).split())
    quote = "Partido da Social Democracia Brasileira (PSDB), ao qual foi filiado até 2021"
    if quote not in text or "Em 1988, foi um dos fundadores" not in text:
        raise ValueError("STATE_GOVERNMENT_MEMBERSHIP_EVIDENCE_MISSING")
    for row in records:
        if "Alckmin" in row["name"]:
            row.update(
                political_party_abbreviation="PSDB",
                political_party_code="historical:PSDB",
                political_party_status="verified_continuous_historical_membership",
                political_party_year_start=1988,
                political_party_year_end=2021,
                political_party_evidence=[evidence(artifact, "p.8 " + quote)],
            )
    return records


def accounting_periods(artifacts):
    cabral = " ".join(document_text(artifacts["cabral_career"]).split())
    quote = "de janeiro de 2007 até 03 de abril de 2014"
    rows = [
        documented_exercise(
            artifacts["cabral_career"],
            "Sérgio Cabral",
            "RJ",
            "2007-01-01",
            "2014-04-04",
            quote,
            cabral,
        )
    ]
    accounts = " ".join(document_text(artifacts["accounts_2018"]).split())
    periods = (
        ("Luiz Fernando Pezão", "2018-01-01", "2018-11-29", "(01.01 a 28.11.2018)"),
        ("Francisco Dornelles", "2018-11-29", "2019-01-01", "(29.11 a 31.12.2018)"),
    )
    for name, start, end, passage in periods:
        row = documented_exercise(
            artifacts["accounts_2018"], name, "RJ", start, end, passage, accounts
        )
        row["evidence"][0]["locator"] = "Contas de governo2018: " + name + " " + passage
        rows.append(row)
    return rows
