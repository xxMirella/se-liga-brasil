"""Transfer domains normalized independently from transport and personal identity."""

from datetime import datetime

from normalization.scalars import normalize_date, normalize_digits, normalize_money, normalize_text
from service.ingestion.contracts import IngestionError


def normalize_api_date(value):
    text = normalize_text(value)
    if text is None:
        return None
    # Validate the whole timestamp before retaining its explicit calendar date.
    try:
        datetime.fromisoformat(text)
    except ValueError as error:
        raise IngestionError("TRANSFEREGOV_INVALID_DATE") from error
    return normalize_date(text.split("T", 1)[0], date_format="%Y-%m-%d")


def normalize_organization(row, prefix, role):
    document = normalize_digits(row.get("cnpj_" + prefix), required=False)
    name = normalize_text(row.get("nm_" + prefix))
    if document is None and name is None:
        return None
    if document is not None and len(document) != 14:
        raise IngestionError("TRANSFEREGOV_INVALID_CNPJ_LENGTH")
    return {"role": role, "corporate_document": document, "name": name}


def normalize_proposal(row):
    roles = (
        ("ente_recebedor", "recipient"),
        ("executor", "executor"),
        ("terceiro_signatario", "third_signatory"),
    )
    organizations = [normalize_organization(row, prefix, role) for prefix, role in roles]
    return {
        "record_key": normalize_digits(row.get("id_proposta")),
        "object_description": normalize_text(row.get("ds_objeto")),
        "status": normalize_text(row.get("situacao_proposta")),
        "proposal_date": normalize_api_date(row.get("dt_proposta")),
        "planned_amount": normalize_money(row.get("nr_vlr_total"), decimal_separator="."),
        "organizations": [item for item in organizations if item is not None],
        "valid_from": None,
        "valid_until": None,
    }


def normalize_partnership(row):
    return {
        "record_key": normalize_digits(row.get("id_parceria")),
        "proposal_key": normalize_digits(row.get("id_proposta")),
        "status": normalize_text(row.get("in_situacao_parceria")),
        "signed_on": normalize_api_date(row.get("dh_assinatura")),
        "execution_authorized_on": normalize_api_date(row.get("dh_autorizacao_execucao")),
        "valid_from": None,
        "valid_until": None,
    }


def normalize_payment_order(row):
    return {
        "record_key": normalize_digits(row.get("id_op")),
        "financial_document_key": normalize_digits(row.get("id_documento_habil")),
        "status": normalize_text(row.get("in_situacao_op")),
        "issued_on": normalize_api_date(row.get("dt_emissao_op")),
        "bank_order_issued_on": normalize_api_date(row.get("dt_emissao_ordem_bancaria")),
        "ordered_amount": normalize_money(row.get("vl_ordem_pagamento"), decimal_separator="."),
        # An order, including an issued bank order, does not prove final execution.
        "executed_amount": None,
    }


def normalize_special_action(row):
    return {
        "record_key": normalize_digits(row.get("id_plano_acao")),
        "object_description": normalize_text(row.get("nome_objeto")),
        "status": normalize_text(row.get("situacao_plano_acao")),
        "accepted_on": normalize_api_date(row.get("data_aceite_plano_acao")),
        "amendment_number": normalize_digits(
            row.get("numero_emenda_parlamentar_plano_acao"), required=False
        ),
        "operating_amount": normalize_money(
            row.get("valor_custeio_plano_acao"), decimal_separator="."
        ),
        "investment_amount": normalize_money(
            row.get("valor_investimento_plano_acao"), decimal_separator="."
        ),
        "person_id": None,
        "person_link_status": "requires_reviewed_identity",
    }


def normalize_amendment_indication(row):
    return {
        "record_key": normalize_digits(row.get("id_indicacao_beneficiario_emenda_parlamentar")),
        "beneficiary_key": normalize_digits(
            row.get("id_beneficiario_emenda_parlamentar"), required=False
        ),
        "supporter_type": normalize_text(row.get("tp_apoiador")),
        "person_id": None,
        "person_link_status": "requires_reviewed_identity",
    }


NORMALIZERS = {
    "parceria": normalize_partnership,
    "proposta": normalize_proposal,
    "ordem-pagamento": normalize_payment_order,
    "planos-acao-especiais": normalize_special_action,
    "indicacao-beneficiario-emenda-parlamentar": normalize_amendment_indication,
}
