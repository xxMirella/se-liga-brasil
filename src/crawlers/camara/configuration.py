"""Bounded official-source acquisition for missing parliamentary data."""

from dataclasses import dataclass
from pathlib import Path

from service.ingestion.contracts import SourceDescriptor

API_BASE = "https://dadosabertos.camara.leg.br/api/v2/"
PORTAL_BASE = "https://www.camara.leg.br/deputados/"
OFFICIAL_HOSTS = frozenset({"dadosabertos.camara.leg.br", "www.camara.leg.br"})
PARSER_VERSION = "camara-enrichment-python-v5"
SOURCE = SourceDescriptor("camara", "Câmara dos Deputados", "https://www.camara.leg.br")


@dataclass(frozen=True)
class CrawlerConfiguration:
    storage_directory: Path
    max_download_bytes: int = 20 * 1024**2
    max_run_download_bytes: int = 200 * 1024**2
    request_timeout_seconds: int = 60
    max_attempts: int = 3
    force_recheck_after_hours: int = 24
    max_pages: int = 100
    max_people: int = 25
    batch_size: int = 500
