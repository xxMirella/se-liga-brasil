"""Stage only personally verified salaries; preserve all original API rows on disk."""

from dataclasses import asdict

from crawlers.senado.payroll import normalize_monthly_salary
from crawlers.senado.payroll_acquisition import acquire_monthly_payroll, match_payroll_entries
from crawlers.senado.staging import stage_records
from service.ingestion.contracts import IngestionError
from service.observability.reporting import describe_error


def collect_verified_salary(repository, acquisition, profile):
    if profile.get("identityMethod") not in {"validated_cpf", "unique_full_name_birth_date"}:
        raise IngestionError("SENADO_PAYROLL_PROFILE_NOT_VERIFIED")
    snapshot = shared_payroll_snapshot(acquisition)
    recipient_key, rows = match_payroll_entries(snapshot, profile)
    salary = normalize_monthly_salary(rows, profile, recipient_key, snapshot.period)
    salary["administrativeRegistrySequence"] = next(
        iter(snapshot.recipients_by_name[salary["normalizedRecipientName"]])
    )
    salary["identityEvidence"] = [
        *salary["identityEvidence"],
        {
            "url": snapshot.registry_artifact.resource.url,
            "sha256": snapshot.registry_artifact.sha256,
        },
    ]
    staged = stage_records(snapshot.payroll_artifact, acquisition.configuration, [salary])
    summary = repository.ingest_validated_artifact(staged, acquisition.configuration.batch_size)
    return {
        "competence": salary["competence"],
        "payroll_entries": len(rows),
        "source_rows": snapshot.source_rows,
        **asdict(summary),
    }


def shared_payroll_snapshot(acquisition):
    if acquisition.payroll_error is not None:
        raise IngestionError(acquisition.payroll_error["code"], acquisition.payroll_error)
    if acquisition.payroll_snapshot is None:
        try:
            acquisition.payroll_snapshot = acquire_monthly_payroll(acquisition)
        except Exception as error:
            acquisition.payroll_error = describe_error(error)
            raise
    return acquisition.payroll_snapshot
