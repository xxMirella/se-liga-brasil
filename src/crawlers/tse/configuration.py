"""Validated runtime configuration; operational limits are explicit."""

from dataclasses import dataclass
from pathlib import Path

from service.ingestion.contracts import RESOURCE_KINDS, IngestionError, SourceDescriptor
from storage.files import load_json

OFFICIAL_HOSTS = frozenset({"dadosabertos.tse.jus.br", "cdn.tse.jus.br"})
CATALOG_API = "https://dadosabertos.tse.jus.br/api/3/action/"
UFS = frozenset(
    [
        "AC",
        "AL",
        "AP",
        "AM",
        "BA",
        "CE",
        "DF",
        "ES",
        "GO",
        "MA",
        "MT",
        "MS",
        "MG",
        "PA",
        "PB",
        "PE",
        "PI",
        "PR",
        "RJ",
        "RN",
        "RS",
        "RO",
        "RR",
        "SC",
        "SP",
        "SE",
        "TO",
        "BR",
        "ZZ",
    ]
)


@dataclass(frozen=True)
class CrawlerConfiguration:
    storage_directory: Path
    years: tuple[int, ...] = (2026,)
    ufs: tuple[str, ...] = ()
    office_codes: tuple[str, ...] = ()
    kinds: tuple[str, ...] = RESOURCE_KINDS
    batch_size: int = 500
    max_download_bytes: int = 1024**3
    max_run_download_bytes: int = 10 * 1024**3
    max_entry_bytes: int = 512 * 1024**2
    max_archive_expanded_bytes: int = 4 * 1024**3
    request_timeout_seconds: int = 180
    max_attempts: int = 3
    force_recheck_after_hours: int = 24

    def __post_init__(self) -> None:
        invalid_year = any(year < 1945 or year > 2200 for year in self.years)
        if invalid_year or not set(self.ufs) <= UFS or not set(self.kinds) <= set(RESOURCE_KINDS):
            raise IngestionError("INVALID_CRAWLER_SCOPE")
        if any(not code.isdigit() for code in self.office_codes):
            raise IngestionError("INVALID_CRAWLER_SCOPE")
        limits = (
            self.batch_size,
            self.max_download_bytes,
            self.max_run_download_bytes,
            self.max_entry_bytes,
            self.max_archive_expanded_bytes,
            self.request_timeout_seconds,
            self.max_attempts,
            self.force_recheck_after_hours,
        )
        if not all(isinstance(value, int) and value > 0 for value in limits):
            raise IngestionError("INVALID_CRAWLER_LIMIT")
        if self.batch_size > 5000 or self.max_attempts > 5:
            raise IngestionError("EXCESSIVE_CRAWLER_LIMIT")

    @property
    def scope_key(self) -> str:
        uf_scope = ",".join(sorted(self.ufs)) or "all"
        if self.office_codes:
            return f"{uf_scope};offices={','.join(sorted(self.office_codes))}"
        return uf_scope


def load_configuration(path: Path, overrides: dict) -> CrawlerConfiguration:
    values = load_json(path)
    values.update({key: value for key, value in overrides.items() if value is not None})
    values["storage_directory"] = Path(values["storage_directory"]).resolve()
    for name in ("years", "ufs", "kinds", "office_codes"):
        values[name] = tuple(values.get(name, ()))
    return CrawlerConfiguration(**values)


TSE_SOURCE = SourceDescriptor(
    "tse", "Tribunal Superior Eleitoral", "https://dadosabertos.tse.jus.br"
)
