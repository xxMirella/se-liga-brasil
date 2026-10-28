"""Annual occurrence evidence does not assert uninterrupted occupancy or invented day dates."""

from crawlers.state_government.parsing import evidence, source_exercise
from service.state_government_history.document_text import document_text
from service.state_government_history.provenance import documented_exercise

ANNUAL_OBSERVATIONS = (
    (
        "pezao_2015",
        "Luiz Fernando Pezão",
        2015,
        2015,
        "governador do Rio de Janeiro, Luiz Fernando Pezão",
    ),
    (
        "pezao_2016",
        "Luiz Fernando Pezão",
        2016,
        2016,
        "sancionada pelo governador Luiz Fernando Pezão (MDB) em janeiro de 2016",
    ),
    ("pezao_2017", "Luiz Fernando Pezão", 2017, 2017, "governador do Rio, Luiz Fernando Pezão"),
    (
        "accounts_2020",
        "Wilson Witzel",
        2020,
        2020,
        ("Em 2020, o Poder Executivo contou com a administração de Wilson Witzel e Cláudio Castro"),
    ),
    (
        "accounts_2020",
        "Cláudio Castro",
        2020,
        2020,
        ("Em 2020, o Poder Executivo contou com a administração de Wilson Witzel e Cláudio Castro"),
    ),
    ("garotinho", "Anthony Garotinho", 1999, 2002, "governador do Rio de Janeiro (1999-2002)"),
    (
        "benedita",
        "Benedita da Silva",
        2002,
        2002,
        "Governador(a), RJ, Partido: PT, Período: 2002 a 2002",
    ),
    (
        "dornelles_2016",
        "Francisco Dornelles",
        2016,
        2016,
        "governador em exercício, Francisco Dornelles",
    ),
    ("witzel", "Wilson Witzel", 2019, 2019, "atual governador, Wilson Witzel"),
)


def annual_observation(artifact, name, first, last, quote):
    text = " ".join(document_text(artifact).split())
    if quote not in text:
        raise ValueError("STATE_GOVERNMENT_ANNUAL_OBSERVATION_NOT_FOUND:" + name)
    result = source_exercise(name, "RJ", name)
    result.update(
        year_start=first,
        year_end=last,
        date_precision="year",
        source_url=artifact.resource.url,
        evidence=[evidence(artifact, quote)],
    )
    return result


def additional_annual_observations(artifacts):
    records = [
        annual_observation(artifacts[key], name, first, last, quote)
        for key, name, first, last, quote in ANNUAL_OBSERVATIONS
    ]
    records.append(
        documented_exercise(
            artifacts["pezao_accession"],
            "Luiz Fernando Pezão",
            "RJ",
            "2014-04-04",
            None,
            "assumiu o cargo de governador no dia 4 de abril",
        )
    )
    records[-1]["observed_through"] = "2014-10-05"
    return records


def extend_verified_observations(records, artifacts):
    serra = document_text(artifacts["serra_exit"])
    freitas = " ".join(document_text(artifacts["freitas_2026"]).split())
    if "cargo que exerce desde 2007" not in serra:
        raise ValueError("STATE_GOVERNMENT_SERRA_PERIOD_NOT_FOUND")
    quote = (
        "Documento assinado eletronicamente por Tarcísio de Freitas, "
        "Governador do Estado, em 26/02/2026"
    )
    if quote not in freitas:
        raise ValueError("STATE_GOVERNMENT_FREITAS_SIGNATURE_NOT_FOUND")
    for row in records:
        if row["name"] == "José Serra" and row.get("exercise_kind") == "holder":
            row["observed_through"] = "2010-03-31"
            row["evidence"].append(evidence(artifacts["serra_exit"], "cargo que exerce desde 2007"))
        if row["name"] == "Tarcísio Gomes de Freitas":
            row["observed_through"] = "2026-02-26"
            row["evidence"].append(evidence(artifacts["freitas_2026"], quote))
    return records


def extend_recent_official_observations(records, artifacts):
    sources = (
        (
            "Tarcísio Gomes de Freitas",
            "freitas_september",
            "2026-09-09",
            "TARCÍSIO DE FREITAS",
            "DE 09 DE SETEMBRO DE 2026",
        ),
        (
            "Ricardo Couto",
            "couto_october",
            "2026-10-16",
            "assinado pelo governador em exercício, desembargador Ricardo Couto",
            "16 de outubro de 2026",
        ),
    )
    for name, key, observed_through, quote, date_quote in sources:
        text = document_text(artifacts[key])
        if quote not in text or date_quote not in text:
            raise ValueError("STATE_GOVERNMENT_RECENT_OBSERVATION_NOT_FOUND:" + name)
        for row in records:
            if row["name"] == name and not row.get("ends_before"):
                row["observed_through"] = observed_through
                row["evidence"].append(evidence(artifacts[key], quote + " / " + date_quote))
    return records
