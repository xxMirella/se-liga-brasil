"""Explicit scope and acquisition limits for ALESP payroll publications."""

import re
from dataclasses import dataclass
from pathlib import Path

from service.ingestion.contracts import IngestionError, SourceDescriptor
from storage.files import load_json

OFFICIAL_HOSTS = frozenset(
    {"www.al.sp.gov.br", "al.sp.gov.br", "legis-api-portal-prd.al.sp.gov.br"}
)
PAYROLL_INDEX_URL = "https://www.al.sp.gov.br/alesp/folha-de-pagamento-deputados/"
ALESP_PARSER_VERSION = "alesp-payroll-python-v1"
ALESP_SOURCE = SourceDescriptor(
    "alesp", "Assembleia Legislativa de São Paulo", "https://www.al.sp.gov.br"
)


@dataclass(frozen=True)
class CrawlerConfiguration:
    storage_directory: Path
    years: tuple[int, ...] = ()
    months: tuple[str, ...] = ()
    kinds: tuple[str, ...] = ("deputy_payroll",)
    batch_size: int = 500
    max_download_bytes: int = 10 * 1024**2
    max_run_download_bytes: int = 100 * 1024**2
    request_timeout_seconds: int = 60
    max_attempts: int = 3
    force_recheck_after_hours: int = 24

    def __post_init__(self) -> None:
        if self.kinds != ("deputy_payroll",):
            raise IngestionError("INVALID_CRAWLER_SCOPE")
        if any(not 2000 <= year <= 2200 for year in self.years):
            raise IngestionError("INVALID_CRAWLER_SCOPE")
        if any(not re.fullmatch(r"20\d{2}-(?:0[1-9]|1[0-2])", month) for month in self.months):
            raise IngestionError("INVALID_CRAWLER_SCOPE")
        limits = (
            self.batch_size,
            self.max_download_bytes,
            self.max_run_download_bytes,
            self.request_timeout_seconds,
            self.max_attempts,
            self.force_recheck_after_hours,
        )
        if any(not isinstance(value, int) or value <= 0 for value in limits):
            raise IngestionError("INVALID_CRAWLER_LIMIT")
        if self.batch_size > 5000 or self.max_attempts > 5:
            raise IngestionError("EXCESSIVE_CRAWLER_LIMIT")

    @property
    def scope_key(self) -> str:
        return "alesp:deputy_payroll"


def load_configuration(path: Path, overrides: dict) -> CrawlerConfiguration:
    values = load_json(path, {})
    values.update({key: value for key, value in overrides.items() if value is not None})
    values["storage_directory"] = Path(values.get("storage_directory", "data/alesp")).resolve()
    for key in ("years", "months", "kinds"):
        if key in values:
            values[key] = tuple(values[key])
    return CrawlerConfiguration(**values)
