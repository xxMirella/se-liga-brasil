"""Qualified reconciliation of a stale titular card using two separately dated official proofs."""

import re
from html import unescape

from crawlers.alrr.roster import parse_directory_members
from parsing.html import decode_html
from service.ingestion.contracts import IngestionError

GOVERNOR_ID = "https://al.rr.leg.br/deputados/soldado-sampaio/"


def reconcile_current_directory(directory, substitution, government):
    replacement_text, government_text = (
        plain_text(payload) for payload in [substitution, government]
    )
    required_replacement = [
        "Rogério Borges",
        "assume a vaga deixada por Soldado Sampaio",
        "novamente temos 24 deputados",
    ]
    if not all(proof in replacement_text for proof in required_replacement):
        raise IngestionError("ALRR_FORMAL_REPLACEMENT_PROOF_MISSING")
    if (
        "19 de outubro de 2026" not in government_text
        or "O governador Soldado Sampaio recebeu nesta quinta-feira, 15" not in government_text
    ):
        raise IngestionError("ALRR_OCTOBER_GOVERNMENT_OBSERVATION_MISSING")
    members = parse_directory_members(directory)
    excluded = [row for row in members if row["provider_subject_id"] == GOVERNOR_ID]
    successors = [row for row in members if row["name"] == "Rogério da Silva Borges"]
    if len(members) != 25 or len(excluded) != 1 or len(successors) != 1:
        raise IngestionError("ALRR_DIRECTORY_REPLACEMENT_IDENTITIES_AMBIGUOUS")
    return [row for row in members if row["provider_subject_id"] != GOVERNOR_ID], excluded[0]


def plain_text(payload):
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", decode_html(payload))))
