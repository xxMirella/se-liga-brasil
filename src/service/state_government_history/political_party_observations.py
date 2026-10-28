"""Contemporaneous labels are dated observations, never full-term affiliation certificates."""

from crawlers.state_government.parsing import evidence
from service.state_government_history.document_text import document_text

OBSERVATIONS = (
    ("Márcio França", "franca", "2018-04-06", "PSB", "então vice, do PSB"),
    ("Márcio França", "doria", "2019-01-01", "PSB", "governador Márcio França (PSB)"),
    ("João Doria", "doria", "2019-01-01", "PSDB", "governador João Doria (PSDB)"),
    (
        "Luiz Fernando Pezão",
        "pezao_accession",
        "2014-10-05",
        "PMDB",
        "Luiz Fernando de Souza Pezão (PMDB)",
    ),
)


def append_contemporaneous_political_party_observations(records, artifacts):
    by_name = {}
    for name, key, observed_on, abbreviation, quote in OBSERVATIONS:
        artifact = artifacts[key]
        if quote not in document_text(artifact):
            raise ValueError("STATE_GOVERNMENT_PARTY_OBSERVATION_NOT_FOUND:" + name)
        by_name.setdefault(name, []).append(
            {
                "abbreviation": abbreviation,
                "observed_on": observed_on,
                "context": "contemporaneous_official_label_not_continuous_affiliation",
                "evidence": [evidence(artifact, quote)],
            }
        )
    for row in records:
        if row["name"] in by_name:
            row["political_party_observations"] = by_name[row["name"]]
    return records
