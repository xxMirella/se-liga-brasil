"""Compose the ALESP source pipeline without coupling services to CLI arguments."""

from crawlers.alesp.adapter import AlespCrawlerAdapter
from crawlers.alesp.affiliations import save_alesp_affiliation_reports
from crawlers.alesp.configuration import PAYROLL_INDEX_URL
from crawlers.alesp.identity import collect_identity_evidence
from crawlers.alesp.reviewed_identity import collect_reviewed_identities
from database.political_party_verification import verify_payroll_political_parties
from service.crawling.source_pipeline import run_source_pipeline
from service.identity_resolution.payroll import resolve_payroll_identities
from storage.files import save_json


def run_alesp_pipeline(phase, configuration, client, repository=None):
    result = (
        {"artifacts": [], "failures": []}
        if phase == "resolve-identities"
        else run_source_pipeline(phase, configuration, client, repository, AlespCrawlerAdapter())
    )
    if repository is not None and phase in {"run", "ingest", "resolve-identities"}:
        subjects = collect_identity_evidence(configuration, client)
        reviewed_cases = collect_reviewed_identities(configuration, client)
        identity = resolve_payroll_identities(
            repository.connection,
            repository.source_id,
            PAYROLL_INDEX_URL,
            subjects,
            uf="SP",
            office_code="7",
            reviewed_cases=reviewed_cases,
        )
        result["affiliation_reports"] = save_alesp_affiliation_reports(
            repository.connection, repository.source_id, PAYROLL_INDEX_URL, identity["resolutions"]
        )
        result["political_party_verification"] = verify_payroll_political_parties(
            repository.connection, repository.source_id, PAYROLL_INDEX_URL
        )
        save_json(configuration.storage_directory / "identity-resolution.json", identity)
        result["identity_resolution"] = {
            key: value
            for key, value in identity.items()
            if key not in {"resolutions", "unresolved"}
        }
        result["identity_unresolved"] = identity["unresolved_recipients"]
        rows = repository.connection.execute(
            "SELECT identity_status,count(*) AS total FROM se_liga_brasil.person_payroll_payment "
            "WHERE source_id=%s GROUP BY identity_status",
            (repository.source_id,),
        ).fetchall()
        result["payroll_identity_coverage"] = {row["identity_status"]: row["total"] for row in rows}
    return result
