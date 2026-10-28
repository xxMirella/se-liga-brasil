"""Validate reviewed presidential claims against archived official documents."""

import subprocess
from copy import deepcopy

from crawlers.presidency.parsing import extract_chronology_text
from crawlers.presidency.reviewed_party_periods import REVIEWED_PRESIDENTIAL_PARTY_PERIODS
from service.ingestion.contracts import IngestionError
from service.presidential_history.party_periods import apply_presidential_party_periods


def collect_presidential_party_periods(acquisition, exercises, reviewed_transcriptions):
    sources, claims = {}, []
    for claim in REVIEWED_PRESIDENTIAL_PARTY_PERIODS:
        url = claim["source_url"]
        if url not in sources:
            sources[url] = acquire_claim_source(acquisition, url, reviewed_transcriptions)
        evidence, text = sources[url]
        if claim["locator"] not in text:
            raise IngestionError("PRESIDENTIAL_PARTY_CLAIM_SOURCE_CHANGED")
        verified = deepcopy(claim)
        verified["evidence"] = [dict(evidence, locator=claim["locator"])]
        if url.startswith("https://neamp.pucsp.br/"):
            verified["evidence"][0].update(
                source_type="original_research_government_dataset",
                publisher="PUC-SP / Núcleo de Estudos em Arte, Mídia e Política",
            )
        if url.startswith("https://repositorio.unb.br/"):
            verified["evidence"][0].update(
                source_type="original_research_doctoral_thesis",
                publisher="Universidade de Brasília / Instituto de Ciência Política",
                author="Rodrigo Lentz", page_label="13", footnote="2",
            )
        if claim["political_party"] in {"PMDB", "MDB"}:
            verified["evidence"].append(reviewed_transcriptions["pmdb_mdb_name_change"])
        for supporting in claim.get("supporting_sources", []):
            verified["evidence"].append(supporting_party_claim_evidence(
                acquisition, sources, supporting, reviewed_transcriptions,
            ))
        claims.append(verified)
    return apply_presidential_party_periods(exercises, claims)


def supporting_party_claim_evidence(acquisition, sources, supporting, transcriptions):
    url = supporting["url"]
    if url not in sources:
        sources[url] = acquire_claim_source(acquisition, url, transcriptions)
    evidence, text = sources[url]
    if not all(locator in text for locator in supporting["locators"]):
        raise IngestionError("PRESIDENTIAL_PARTY_SUPPORTING_SOURCE_CHANGED")
    return dict(evidence, locator="; ".join(supporting["locators"]))


def acquire_claim_source(acquisition, url, reviewed_transcriptions):
    reviewed = reviewed_transcriptions.get(url)
    if reviewed:
        return reviewed["evidence"], reviewed["transcription"]
    artifact = acquisition.acquire(url, file_suffix=".pdf") if url.endswith(".pdf") else (
        acquisition.acquire(url))
    return (
        qualified_source_metadata({
            "url": url,
            "sha256": artifact.sha256,
            "fetched_at": artifact.fetched_at,
            "source_type": "official_archived_historical_document",
        }, url),
        claim_document_text(artifact),
    )


def qualified_source_metadata(evidence, url):
    if url.startswith("https://periodicos.fclar.unesp.br/"):
        evidence.update(source_type="original_research_journal_article",
                        publisher="UNESP / Estudos de Sociologia", author="Lucila Scavone",
                        page_label="194", published_on="2020-07-24", doi="10.52780/res.13979")
    if url.startswith("https://files.ufgd.edu.br/"):
        evidence.update(source_type="original_research_doctoral_thesis",
                        publisher="Universidade Federal da Grande Dourados",
                        author="Carlos Eduardo Ferreira Soares", page_label="36", footnote="9",
                        publication_year=2025)
    return evidence


def claim_document_text(artifact):
    payload = artifact.path.read_bytes()
    if payload.startswith(b"%PDF"):
        extracted = subprocess.run(
            ["pdftotext", "-raw", str(artifact.path), "-"],
            check=True, capture_output=True, timeout=30,
        )
        return " ".join(extracted.stdout.decode("utf-8").split())
    return " ".join(extract_chronology_text(payload).split())
