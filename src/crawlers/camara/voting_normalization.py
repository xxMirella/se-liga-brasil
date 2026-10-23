"""Published voting observations, with no invented absence, result or vote modality."""

import re
from datetime import date

from crawlers.camara.configuration import API_BASE
from normalization.scalars import normalize_text
from normalization.text import fold_text
from service.ingestion.contracts import IngestionError

VOTE_CHOICES = {
    "sim": ("yes", "voted"),
    "favoravel": ("yes", "voted"),
    "nao": ("no", "voted"),
    "contrario": ("no", "voted"),
    "abstencao": ("abstention", "voted"),
    "obstrucao": ("obstruction", "voted"),
    "art. 17": (None, "presiding"),
    "artigo 17": (None, "presiding"),
    "ausente": (None, "absent"),
    "ausencia": (None, "absent"),
    "ausencia justificada": (None, "excused"),
}


def voting_identifier(row):
    key = normalize_text(row.get("id"), required=True, max_length=100)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,99}", key):
        raise IngestionError("INVALID_CAMARA_VOTING_IDENTIFIER")
    if row.get("uri") != API_BASE + "votacoes/" + key:
        raise IngestionError("CAMARA_VOTING_URI_MISMATCH")
    return key


def normalize_voting_event(discovery, detail):
    key = voting_identifier(discovery)
    if voting_identifier(detail) != key or detail.get("data") != discovery.get("data"):
        raise IngestionError("CAMARA_VOTING_DETAIL_MISMATCH")
    try:
        occurred_on = date.fromisoformat(detail["data"]).isoformat()
    except (KeyError, TypeError, ValueError) as error:
        raise IngestionError("CAMARA_VOTING_DATE_CHANGED") from error
    subject = normalize_text(detail.get("descUltimaAberturaVotacao"))
    subject = subject or normalize_text(detail.get("descricao"))
    subject = subject or normalize_text(discovery.get("proposicaoObjeto"))
    return {
        "voting_id": "camara:voting:" + key,
        "institution_code": "camara",
        "occurred_on": occurred_on,
        "date_precision": "day",
        "voting_subject": subject,
        "round_number": published_round_number(subject, detail.get("descricao")),
        "official_url": detail["uri"],
    }


def published_round_number(subject, result_description):
    """Use an explicit event round; references to two rounds prove neither one."""
    pattern = r"\b(primeiro|segundo|1[ºo]?|2[ºo]?)\s+turno\b"
    matches = re.findall(pattern, subject or "", re.I)
    result = normalize_text(result_description) or ""
    approved = re.match(r"Aprovad[ao]s?,?\s+em\s+(.+)", result, re.I)
    if approved:
        matches.extend(re.findall(pattern, approved[1], re.I))
    numbers = {1 if value.lower() in {"primeiro", "1", "1º", "1o"} else 2 for value in matches}
    return numbers.pop() if len(numbers) == 1 else None


def normalize_individual_vote(row):
    code = normalize_text(row.get("tipoVoto"), max_length=100)
    choice, status = VOTE_CHOICES.get(fold_text(code or ""), (None, "unknown"))
    return {"vote_choice": choice, "participation_status": status}


def identified_matter_uri(discovery):
    uri = normalize_text(discovery.get("uriProposicaoObjeto"), max_length=2048)
    if uri is None:
        return None
    prefix = API_BASE + "proposicoes/"
    if not uri.startswith(prefix) or not re.fullmatch(r"[1-9][0-9]*", uri.removeprefix(prefix)):
        raise IngestionError("CAMARA_VOTING_PROPOSITION_URI_MISMATCH")
    return uri


def matter_fields(matter, official_url):
    if matter is None:
        return {
            "matter_kind": None,
            "matter_number": None,
            "matter_year": None,
            "matter_name": None,
            "description": None,
            "description_origin": "unknown",
            "official_url": official_url,
        }
    kind = normalize_text(matter.get("siglaTipo"))
    number = normalize_text(matter.get("numero"))
    year = matter.get("ano")
    if year is not None and (type(year) is not int or not 1800 <= year <= 2200):
        raise IngestionError("CAMARA_VOTING_PROPOSITION_YEAR_CHANGED")
    name = f"{kind} {number}/{year}" if kind and number and year else None
    description = normalize_text(matter.get("ementa"), max_length=8000)
    return {
        "matter_kind": kind,
        "matter_number": number,
        "matter_year": year,
        "matter_name": name,
        "description": description,
        "description_origin": "official_text" if description else "unknown",
        "official_url": official_url,
    }


def related_matter_uri(event):
    explicit = identified_matter_uri(event["discovery"])
    if explicit:
        return explicit
    affected = event["detail"].get("proposicoesAfetadas") or []
    if len(affected) != 1:
        return None
    return identified_matter_uri({"uriProposicaoObjeto": affected[0].get("uri")})
