"""Bounded collection callable by orchestration with an existing ingestion repository."""

from dataclasses import asdict

from crawlers.cmsp.acquisition import annual_resources
from crawlers.cmsp.identity import index_reviewed_bindings
from crawlers.cmsp.staging import stage_partition
from service.ingestion.contracts import IngestionError


def collect_municipal_legislation(
    acquisition,
    years,
    *,
    domains=("projects", "authorship", "deliberations"),
    reviewed_bindings=(),
    repository=None,
):
    """Yield only fully parsed partitions; no repository means local analysis only."""
    bindings = index_reviewed_bindings(reviewed_bindings)
    for position, resource in enumerate(annual_resources(years, domains), 1):
        if position > acquisition.configuration.max_resources:
            raise IngestionError("CMSP_RESOURCE_LIMIT_EXCEEDED")
        artifact = acquisition.acquire(resource)
        artifact_bindings = {
            name: binding
            for name, binding in bindings.items()
            if binding.artifact_sha256 == artifact.sha256
        }
        validated = stage_partition(artifact, acquisition.configuration, artifact_bindings)
        result = {
            "year": resource.year,
            "domain": resource.kind,
            "artifactSha256": artifact.sha256,
            "records": validated.summary,
            "validatedArtifact": validated,
            "coverage": "partial" if validated.summary["rejected"] else "partition_parsed",
            "identityCoverage": "reviewed_evidence_only",
            "historicalCompleteness": "not_asserted",
        }
        if repository is not None:
            result["ingestion"] = asdict(
                repository.ingest_validated_artifact(
                    validated,
                    acquisition.configuration.batch_size,
                )
            )
        yield result
