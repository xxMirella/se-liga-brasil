"""Download one nominal monthly payroll and registry per collection, with shared limits."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from crawlers.senado.payroll import index_monthly_payroll, index_parliamentary_recipients
from service.ingestion.contracts import DownloadedArtifact, IngestionError

ADMINISTRATIVE_API_BASE = "https://adm.senado.gov.br/adm-dadosabertos/api/v1/"
PARLIAMENTARY_REGISTRY = (
    ADMINISTRATIVE_API_BASE
    + "servidores/servidores?tipoVinculoEquals=PARLAMENTAR&situacaoEquals=ATIVO"
)


@dataclass(frozen=True)
class PayrollSnapshot:
    period: date
    payroll_artifact: DownloadedArtifact
    registry_artifact: DownloadedArtifact
    recipients_by_name: dict
    entries_by_recipient: dict
    payroll_recipients_by_name: dict
    source_rows: int


def previous_payroll_period(today=None):
    today = today or datetime.now(ZoneInfo("America/Belem")).date()
    return (today.replace(day=1) - timedelta(days=1)).replace(day=1)


def acquire_monthly_payroll(acquisition):
    period = previous_payroll_period()
    registry, registry_artifact = acquisition.json_document(
        PARLIAMENTARY_REGISTRY, "senado_parliamentary_payroll_registry"
    )
    recipients = index_parliamentary_recipients(registry)
    document, artifact = acquisition.json_document(
        ADMINISTRATIVE_API_BASE + f"servidores/remuneracoes/{period.year}/{period.month}",
        "senado_payroll",
        resource_year=period.year,
    )
    entries = index_monthly_payroll(document, period)
    return PayrollSnapshot(
        period,
        artifact,
        registry_artifact,
        recipients,
        entries,
        index_payroll_names(entries),
        len(document),
    )


def index_payroll_names(entries):
    from collections import defaultdict

    from normalization.identity import normalize_person_name

    names = defaultdict(set)
    for key, rows in entries.items():
        names[normalize_person_name(rows[0][1]["nome"])].add(key)
    return dict(names)


def match_payroll_entries(snapshot, profile):
    from normalization.identity import normalize_person_name

    name = normalize_person_name(profile["civilName"])
    registry_ids = snapshot.recipients_by_name.get(name, set())
    if len(registry_ids) != 1:
        raise IngestionError("SENADO_PARLIAMENTARY_PAYROLL_IDENTITY_NOT_CONFIRMED")
    # The identically named sequence fields belong to different source namespaces.
    payroll_ids = snapshot.payroll_recipients_by_name.get(name, set())
    if len(payroll_ids) > 1:
        raise IngestionError("SENADO_PAYROLL_NAME_AMBIGUOUS")
    if not payroll_ids:
        raise IngestionError("SENADO_PAYROLL_PERSON_NOT_PUBLISHED")
    recipient_key = next(iter(payroll_ids))
    return recipient_key, snapshot.entries_by_recipient[recipient_key]
