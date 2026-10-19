"""Source-independent ingestion orchestration and structured rejection reporting."""

from dataclasses import asdict

from service.ingestion.contracts import IngestionError, Resource
from service.observability.reporting import describe_error, emit_event, rejection_message
from storage.files import read_json_lines


def report_validation_rejections(validated) -> None:
    for rejection in read_json_lines(validated.rejected_path):
        report_rejection(
            validated.artifact.resource,
            "validate",
            rejection["reasonCode"],
            rejection.get("entryName"),
            rejection.get("rowNumber"),
            rejection.get("details", {}),
        )


def report_rejection(resource, stage, code, entry_name, row_number, context=None) -> None:
    emit_event(
        "rejected",
        stage=stage,
        resource_id=resource.resource_id,
        resource_name=resource.name,
        source_url=resource.url,
        year=resource.year,
        uf=resource.uf or "BR",
        entry_name=entry_name,
        row_number=row_number,
        code=code,
        message=rejection_message(code),
        context=context or {},
    )


def build_resource_failure(resource: Resource, error: Exception, stage: str) -> dict:
    failure = {
        "stage": stage,
        "resource_id": resource.resource_id,
        "resource_name": resource.name,
        "source_url": resource.url,
        "year": resource.year,
        "uf": resource.uf or "BR (arquivo nacional)",
        "kind": resource.kind,
        **describe_error(error),
    }
    emit_event("resource_failed", **failure)
    return failure


def ingest_validation_plan(configuration, repository, validations, failures) -> list[dict]:
    summaries = []
    for validated in validations:
        resource = validated.artifact.resource
        try:
            emit_event(
                "ingest_started",
                resource_name=resource.name,
                total_records=validated.summary["valid"],
            )
            summary = repository.ingest_validated_artifact(validated, configuration.batch_size)
            if summary.rejected:
                for rejection in repository.iter_resource_rejections(resource.resource_id):
                    report_rejection(
                        resource,
                        "ingest",
                        rejection["reason_code"],
                        rejection["entry_name"],
                        rejection["row_number"],
                        rejection["details"],
                    )
            result = {"resource_id": resource.resource_id, "kind": resource.kind, **asdict(summary)}
            summaries.append(result)
            emit_event("ingest", **result)
        except Exception as error:
            failure = build_resource_failure(resource, error, "ingest")
            failures.append(failure)
            repository.reject_resource(resource.resource_id, IngestionError(failure["code"]))
    return summaries
