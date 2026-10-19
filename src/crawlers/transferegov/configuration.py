"""Validated official API contracts and bounded acquisition configuration."""

from dataclasses import dataclass
from pathlib import Path

from service.ingestion.contracts import SourceDescriptor

API_BASE = "https://api-publica.transferegov.gestao.gov.br/"
OFFICIAL_HOSTS = frozenset({"api-publica.transferegov.gestao.gov.br"})
SOURCE = SourceDescriptor("transferegov", "Ministério da Gestão", API_BASE)
PARSER_VERSION = "transferegov-public-v1"
# Deliberately expose only validated filters needed for partitioned acquisition.
ENDPOINT_FILTERS = {
    ("parcerias", "parceria"): frozenset({"id_parceria", "id_proposta", "dh_assinatura"}),
    ("parcerias", "proposta"): frozenset(
        {"id_proposta", "id_programa", "ano_proposta", "sg_uf_recebedor", "cnpj_executor"}
    ),
    ("parcerias", "ordem-pagamento"): frozenset({"id_op", "id_documento_habil", "dt_emissao_op"}),
    ("parcerias", "indicacao-beneficiario-emenda-parlamentar"): frozenset(
        {"id_indicacao_beneficiario_emenda_parlamentar", "id_beneficiario_emenda_parlamentar"}
    ),
    ("especiais", "planos-acao-especiais"): frozenset(
        {"id_plano_acao", "ano_plano_acao", "id_beneficiario", "id_programa"}
    ),
}


@dataclass(frozen=True)
class CrawlerConfiguration:
    storage_directory: Path
    max_download_bytes: int = 20 * 1024**2
    max_run_download_bytes: int = 80 * 1024**2
    max_attempts: int = 3
    request_timeout_seconds: int = 60
    request_min_interval_seconds: float = 1.0
    force_recheck_after_hours: int = 24
    max_pages: int = 20
    page_size: int = 100
    max_records: int = 2000
    max_partitions: int = 20
