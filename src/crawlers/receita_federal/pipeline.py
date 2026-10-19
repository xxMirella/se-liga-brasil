"""Read each selected snapshot partition once for the whole person batch."""

from dataclasses import dataclass
from datetime import date, datetime

from crawlers.receita_federal.identity import identify_partner, index_people
from crawlers.receita_federal.normalization import (
    normalize_company,
    normalize_company_base,
    normalize_establishment,
    normalize_partner,
)
from crawlers.receita_federal.parsing import iter_partition_rows
from service.ingestion.contracts import IngestionError


@dataclass(frozen=True)
class SnapshotFacts:
    companies: tuple[dict, ...]
    establishments: tuple[dict, ...]
    relationships: tuple[dict, ...]
    completed_partition_hashes: tuple[str, ...]
    snapshot_month: str
    observed_on: str


def source_observed_on(artifact, analysis_as_of):
    observation = datetime.fromisoformat(artifact.fetched_at).date().isoformat()
    if observation > analysis_as_of:
        raise IngestionError("CNPJ_ARTIFACT_AFTER_ANALYSIS_DATE")
    return observation


def add_bounded_fact(facts, key, fact, configuration):
    if key not in facts and len(facts) >= configuration.max_matches:
        raise IngestionError("CNPJ_MATCH_LIMIT_EXCEEDED")
    if key in facts and facts[key] != fact:
        raise IngestionError("CNPJ_CONFLICTING_DUPLICATE")
    facts[key] = fact


def scan_partners(artifacts, people_index, reviewed, configuration, observed_on):
    relationships = {}
    for artifact in artifacts:
        for row in iter_partition_rows(artifact.path, "partners", configuration):
            partner = normalize_partner(row)
            identity = identify_partner(partner, row, people_index, reviewed, artifact.sha256)
            if identity is None:
                continue
            partner.pop("partner_document")
            fact = (
                partner
                | identity
                | {
                    "observed_on": source_observed_on(artifact, observed_on),
                    "source_sha256": artifact.sha256,
                }
            )
            add_bounded_fact(relationships, identity["observation_key"], fact, configuration)
    return relationships


def scan_business_facts(artifacts, company_bases, configuration, kind, observed_on):
    facts = {}
    normalize = normalize_company if kind == "companies" else normalize_establishment
    for artifact in artifacts:
        for row in iter_partition_rows(artifact.path, kind, configuration):
            if normalize_company_base(row[0]) not in company_bases:
                continue
            fact = normalize(row) | {
                "observed_on": source_observed_on(artifact, observed_on),
                "source_sha256": artifact.sha256,
            }
            key = fact.get("cnpj", fact["company_base"])
            add_bounded_fact(facts, key, fact, configuration)
    return tuple(facts.values())


def scan_snapshot(artifacts, people, configuration, *, observed_on, reviewed_relationships=None):
    """Return facts only after all selected partitions finish; never prove historical absence."""
    date.fromisoformat(observed_on)
    unique_artifacts = {artifact.sha256: artifact for artifact in artifacts}
    artifacts = tuple(unique_artifacts.values())
    if not artifacts or len(artifacts) > configuration.max_resources:
        raise IngestionError("CNPJ_RESOURCE_LIMIT_EXCEEDED")
    months = {artifact.resource.dataset for artifact in artifacts}
    if len(months) != 1:
        raise IngestionError("CNPJ_MIXED_SNAPSHOTS")
    groups = group_artifacts(artifacts)
    relationships = scan_partners(
        groups["partners"],
        index_people(people),
        reviewed_relationships or {},
        configuration,
        observed_on,
    )
    bases = {fact["company_base"] for fact in relationships.values()}
    companies = scan_business_facts(
        groups["companies"], bases, configuration, "companies", observed_on
    )
    establishments = scan_business_facts(
        groups["establishments"],
        bases,
        configuration,
        "establishments",
        observed_on,
    )
    return SnapshotFacts(
        companies,
        establishments,
        tuple(relationships.values()),
        tuple(unique_artifacts),
        months.pop(),
        observed_on,
    )


def group_artifacts(artifacts):
    groups = {"companies": [], "establishments": [], "partners": []}
    for artifact in artifacts:
        if artifact.resource.kind not in groups:
            raise IngestionError("CNPJ_UNSUPPORTED_KIND")
        groups[artifact.resource.kind].append(artifact)
    if not groups["partners"]:
        raise IngestionError("CNPJ_PARTNER_PARTITION_REQUIRED")
    return groups


def ingest_snapshot_facts(artifacts, facts, configuration, repository):
    """Use a preconfigured ingestion repository/run; no connection or migration implicit."""
    from crawlers.receita_federal.staging import stage_snapshot_facts

    summaries = []
    for artifact in artifacts:
        validated = stage_snapshot_facts(artifact, facts, configuration)
        if validated.summary["valid"]:
            summaries.append(
                repository.ingest_validated_artifact(validated, configuration.batch_size)
            )
    return tuple(summaries)
