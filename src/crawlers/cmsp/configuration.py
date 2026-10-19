"""Official SPLEGIS endpoints and resource limits."""

from dataclasses import dataclass
from pathlib import Path

from service.ingestion.contracts import SourceDescriptor

API_BASE = "https://splegisws.saopaulo.sp.leg.br/ws/ws2.asmx/"
OFFICIAL_HOSTS = frozenset({"splegisws.saopaulo.sp.leg.br"})
SOURCE = SourceDescriptor("cmsp", "Câmara Municipal de São Paulo", API_BASE)
PARSER_VERSION = "cmsp-splegis-v1"
XML_NAMESPACE = "http://saopaulo.sp.leg.br"


@dataclass(frozen=True)
class CrawlerConfiguration:
    storage_directory: Path
    max_download_bytes: int = 40 * 1024**2
    max_run_download_bytes: int = 100 * 1024**2
    max_attempts: int = 3
    request_timeout_seconds: int = 60
    request_min_interval_seconds: float = 1.0
    force_recheck_after_hours: int = 24
    max_resources: int = 6
    max_records_per_resource: int = 10000
    batch_size: int = 500
