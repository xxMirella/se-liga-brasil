"""Bounded acquisition of official CNPJ snapshot partitions."""

from dataclasses import dataclass
from pathlib import Path

OFFICIAL_HOSTS = frozenset({"arquivos.receitafederal.gov.br", "dadosabertos.rfb.gov.br"})
LAYOUT_URL = "https://www.gov.br/receitafederal/dados/cnpj-metadados.pdf/@@download/file"


@dataclass(frozen=True)
class CrawlerConfiguration:
    storage_directory: Path
    max_download_bytes: int = 100 * 1024**2
    max_run_download_bytes: int = 200 * 1024**2
    max_attempts: int = 3
    request_timeout_seconds: int = 60
    request_min_interval_seconds: float = 1.0
    force_recheck_after_hours: int = 24
    max_resources: int = 3
    max_uncompressed_bytes: int = 500 * 1024**2
    max_records_per_resource: int = 1000000
    max_members_per_resource: int = 2
    max_matches: int = 10000
    batch_size: int = 500
