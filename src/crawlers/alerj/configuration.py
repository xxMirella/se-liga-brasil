"""Restricted acquisition settings for ALERJ institutional evidence."""

from dataclasses import dataclass
from pathlib import Path

from service.ingestion.contracts import SourceDescriptor

PORTAL_BASE = "https://www.alerj.rj.gov.br"
ROSTER_URL = PORTAL_BASE + "/Deputados/QuemSao"
PAYROLL_INDEX_URL = "https://transparencia.alerj.rj.gov.br/section/report/73"
OFFICIAL_HOSTS = frozenset(
    {"www.alerj.rj.gov.br", "www2.alerj.rj.gov.br", "transparencia.alerj.rj.gov.br"}
)
SOURCE = SourceDescriptor("alerj", "Assembleia Legislativa do Rio de Janeiro", PORTAL_BASE)
PARSER_VERSION = "alerj-enrichment-python-v3"


@dataclass(frozen=True)
class CrawlerConfiguration:
    storage_directory: Path
    max_download_bytes: int = 40 * 1024**2
    max_run_download_bytes: int = 100 * 1024**2
    request_timeout_seconds: int = 60
    max_attempts: int = 3
    force_recheck_after_hours: int = 24
    max_people: int = 25
    batch_size: int = 500
