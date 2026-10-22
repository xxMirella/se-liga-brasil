"""Bounded Senate collection settings."""

from dataclasses import dataclass
from pathlib import Path

from service.ingestion.contracts import SourceDescriptor

API_BASE = "https://legis.senado.leg.br/dadosabertos/"
OFFICIAL_HOSTS = frozenset({"legis.senado.leg.br", "adm.senado.gov.br"})
SOURCE = SourceDescriptor("senado", "Senado Federal", "https://www.senado.leg.br")
PARSER_VERSION = "senado-personal-python-v4"


@dataclass(frozen=True)
class SenateConfiguration:
    storage_directory: Path
    max_download_bytes: int = 20 * 1024**2
    max_run_download_bytes: int = 100 * 1024**2
    request_timeout_seconds: int = 60
    max_attempts: int = 3
    force_recheck_after_hours: int = 24
    max_people: int = 25
    batch_size: int = 500
