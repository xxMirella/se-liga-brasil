"""Structured diagnostics without candidate data or database credentials."""

import json
import sys
import traceback
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

from service.ingestion.contracts import IngestionError

ERROR_MESSAGES = {
    "POSTGRES_CONNECTION_REQUIRED": "Configure uma conexão PostgreSQL pelo --env-file.",
    "CRAWLER_ALREADY_RUNNING_LOCALLY": "Já existe um crawler usando esta pasta de dados.",
    "CRAWLER_ALREADY_RUNNING_IN_DATABASE": "Já existe uma ingestão ativa desta fonte neste banco.",
    "RUN_DOWNLOAD_LIMIT_EXCEEDED": "O total de downloads excedeu o limite configurado.",
    "RESOURCE_DOWNLOAD_LIMIT_EXCEEDED": "O arquivo excedeu o limite de download configurado.",
    "CSV_SCHEMA_CHANGED": "O CSV do TSE não contém as colunas esperadas.",
    "ARCHIVE_FORMAT_CHANGED": "O arquivo do TSE não contém os dados no formato esperado.",
    "STAGING_SCOPE_MISMATCH": "O recorte de UF difere do usado na validação; execute run.",
    "NO_VALIDATED_ARTIFACTS": "Nenhum arquivo validado está disponível para ingestão.",
    "HTTP_ATTEMPTS_EXHAUSTED": "As tentativas de acesso à fonte oficial foram esgotadas.",
    "HTTP_ERROR": "A fonte oficial retornou um erro HTTP; consulte o status informado.",
    "UNRESOLVED_HISTORY_IDENTITY": "O histórico não tem vínculo seguro com uma pessoa cadastrada.",
    "CANDIDATE_IDENTITY_NOT_FOUND": "A candidatura vinculada ainda não está cadastrada.",
    "SAME_TIMESTAMP_CONFLICT": "Dados diferentes foram publicados com a mesma data de geração.",
    "REQUIRED_VALUE_MISSING": "Um campo obrigatório está vazio ou marcado como ausente.",
    "INVALID_IDENTIFIER": "O identificador deve conter somente dígitos.",
    "INVALID_DATE": "A data não existe ou está fora do formato esperado.",
    "INVALID_TIMESTAMP": "A data e hora estão fora do formato esperado.",
    "INVALID_MONEY": "O valor monetário não segue o formato esperado para esta fonte.",
    "MONEY_OUT_OF_RANGE": "O valor monetário excede a precisão permitida no banco.",
    "INVALID_TEXT": "O texto excede o limite ou contém caracteres inválidos.",
    "INVALID_UF": "A UF informada não é reconhecida.",
    "INVALID_BIRTH_DATE": "A data de nascimento é posterior à geração dos dados.",
    "INVALID_GENERATION_TIMESTAMP": "A data de geração do arquivo é inválida.",
    "FUTURE_GENERATION_TIMESTAMP": "A data de geração do arquivo está no futuro.",
    "INVALID_ELECTION_ROUND": "O turno da eleição é inválido.",
    "DATASET_YEAR_MISMATCH": "O ano do registro não corresponde ao conjunto de dados.",
    "INVALID_YEAR": "O ano está fora do intervalo aceito.",
    "INVALID_PDF_SIGNATURE": "O documento não contém a assinatura de um arquivo PDF.",
    "UNRECOGNIZED_DOCUMENT_ID": "O nome do documento não permite identificar a candidatura.",
    "DOCUMENT_UF_MISMATCH": "A UF do documento difere da UF do recurso.",
    "DOCUMENT_TOO_LARGE": "O documento excede o tamanho permitido.",
    "DOCUMENT_IDENTITY_CONFLICT": "O CPF diverge do documento já vinculado à pessoa.",
    "BIRTH_DATE_IDENTITY_CONFLICT": "As identidades têm datas de nascimento incompatíveis.",
    "IDENTITY_RELATION_CONFLICT": "A união conflita com relações existentes e exige revisão.",
    "HISTORY_ANCHOR_NOT_FOUND": "A candidatura de referência do histórico não está cadastrada.",
    "HISTORY_MULTIPLE_ANCHORS": "O histórico aponta para pessoas diferentes no mesmo lote.",
    "INVALID_CPF": "O CPF não passou na validação de formato e dígitos verificadores.",
    "INVALID_BOOLEAN": "O campo não contém um valor booleano reconhecido.",
    "ARCHIVE_CHECKSUM_MISMATCH": "O hash do ZIP difere do registrado no download.",
    "VALIDATION_CHECKSUM_MISMATCH": "Um arquivo de staging foi alterado após a validação.",
    "STAGED_RECORD_HASH_MISMATCH": "O conteúdo normalizado difere do hash registrado.",
    "DOCUMENT_CHECKSUM_MISMATCH": "O documento local foi alterado após a validação.",
    "CSV_COLUMN_COUNT_MISMATCH": "A linha contém um número de colunas diferente do cabeçalho.",
    "INVALID_CSV_HEADER": "O cabeçalho CSV está vazio, duplicado ou inválido.",
    "UNSAFE_ARCHIVE_ENTRY": "O ZIP contém um caminho interno inseguro.",
    "ARCHIVE_SYMLINK_REJECTED": "O ZIP contém um link simbólico não permitido.",
    "ARCHIVE_ENTRY_LIMIT_EXCEEDED": "O ZIP excede o número de entradas permitido.",
    "ARCHIVE_EXPANSION_LIMIT_EXCEEDED": "O tamanho descompactado excede o limite permitido.",
    "ARCHIVE_ENTRY_TOO_LARGE": "Uma entrada do ZIP excede o tamanho permitido.",
}
SAFE_DETAIL_FIELDS = frozenset(
    {"missing_headers", "row_number", "status_code", "status", "retry_after_seconds"}
)
EVENT_CONSUMER = ContextVar("event_consumer", default=None)


@contextmanager
def event_display(consumer):
    token = EVENT_CONSUMER.set(consumer)
    try:
        yield
    finally:
        EVENT_CONSUMER.reset(token)


def emit_event(phase: str, **details) -> None:
    consumer = EVENT_CONSUMER.get()
    if consumer is not None:
        consumer({"phase": phase, **details})
        return
    write_event({"phase": phase, **details})


def write_event(event: dict) -> None:
    output = (
        sys.stderr if event["phase"] in {"failed", "resource_failed", "rejected"} else sys.stdout
    )
    print(json.dumps(event, ensure_ascii=False), file=output, flush=True)


def rejection_message(code: str) -> str:
    return ERROR_MESSAGES.get(code, f"Registro rejeitado pela regra {code}.")


def find_error_location(error: Exception) -> dict:
    frames = traceback.extract_tb(error.__traceback__)
    if not frames:
        return {}
    project_root = Path(__file__).resolve().parents[3]
    local_frames = [
        frame
        for frame in frames
        if Path(frame.filename).is_relative_to(project_root)
        and ".venv" not in Path(frame.filename).parts
    ]
    frame = (local_frames or frames)[-1]
    return {"file": frame.filename, "line": frame.lineno, "function": frame.name}


def describe_error(error: Exception) -> dict:
    code = error.code if isinstance(error, IngestionError) else "OPERATION_FAILED"
    message = ERROR_MESSAGES.get(code, "Falha na operação; consulte o código e a localização.")
    details = {}
    if isinstance(error, IngestionError):
        details = {key: value for key, value in error.details.items() if key in SAFE_DETAIL_FIELDS}
    sqlstate = getattr(error, "sqlstate", None)
    if sqlstate:
        details["sqlstate"] = sqlstate
        message = "O PostgreSQL recusou a operação; consulte o SQLSTATE e a localização."
    return {
        "code": code,
        "message": message,
        "error_type": type(error).__name__,
        "location": find_error_location(error),
        **details,
    }
