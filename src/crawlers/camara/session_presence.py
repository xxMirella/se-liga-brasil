"""Explicit official plenary frequencies; no absence is inferred from missing votes."""

from datetime import datetime
from xml.etree import ElementTree

from normalization.text import fold_text
from service.ingestion.contracts import IngestionError

PRESENCE_STATES = {"presenca": "present", "ausencia": "absent", "ausencia justificada": "excused"}


def parse_official_xml(payload):
    if b"<!DOCTYPE" in payload.upper() or b"<!ENTITY" in payload.upper():
        raise IngestionError("UNSAFE_OFFICIAL_PRESENCE_XML")
    try:
        return ElementTree.fromstring(payload)
    except ElementTree.ParseError as error:
        raise IngestionError("INVALID_OFFICIAL_PRESENCE_XML") from error


def parse_presence_roster(payload):
    root = parse_official_xml(payload)
    index = {}
    for member in root.findall("deputado"):
        card = member.findtext("matricula")
        key = member.findtext("ideCadastro")
        if not card or not key or not card.isdecimal() or not key.isdecimal():
            raise IngestionError("CAMARA_PRESENCE_ROSTER_IDENTITY_MISSING")
        if card in index:
            raise IngestionError("CAMARA_PRESENCE_ROSTER_AMBIGUOUS_CARD")
        index[card] = {
            "key": key,
            "name": member.findtext("nomeParlamentar"),
            "uf": member.findtext("uf"),
        }
    if not index:
        raise IngestionError("CAMARA_PRESENCE_ROSTER_EMPTY")
    return index


def parse_daily_session_presence(payload, expected_day):
    root = parse_official_xml(payload)
    try:
        day = datetime.strptime(root.findtext("data"), "%d/%m/%Y %H:%M:%S").date()
        legislature = int(root.findtext("legislatura"))
    except (TypeError, ValueError) as error:
        raise IngestionError("CAMARA_SESSION_PRESENCE_DATE_INVALID") from error
    if day != expected_day:
        raise IngestionError("CAMARA_SESSION_PRESENCE_DATE_MISMATCH")
    records, cards = [], set()
    for member in root.findall("parlamentares/parlamentar"):
        card = member.findtext("carteiraParlamentar")
        if not card or card in cards:
            raise IngestionError("CAMARA_SESSION_PRESENCE_DUPLICATE_OR_MISSING_CARD")
        cards.add(card)
        sessions = [
            parse_session_presence(session, day)
            for session in member.findall("sessoesDia/sessaoDia")
        ]
        records.append(
            {
                "card": card,
                "name": presence_member_name(member),
                "uf": member.findtext("siglaUF"),
                "sessions": sessions,
                "presence_status": presence_state(member.findtext("descricaoFrequenciaDia")),
            }
        )
    if not records:
        raise IngestionError("CAMARA_SESSION_PRESENCE_EMPTY")
    return records, legislature


def presence_state(value):
    return PRESENCE_STATES.get(fold_text(value or ""), "unknown")


def presence_member_name(member):
    name = member.findtext("nomeParlamentar") or ""
    political_party = (member.findtext("siglaPartido") or "").strip()
    uf = (member.findtext("siglaUF") or "").strip()
    suffix = f"-{political_party}/{uf}"
    return name.removesuffix(suffix)


def parse_session_presence(session, day):
    try:
        start = datetime.strptime(session.findtext("inicio"), "%d/%m/%Y %H:%M:%S")
    except (TypeError, ValueError) as error:
        raise IngestionError("CAMARA_SESSION_START_INVALID") from error
    if start.date() != day:
        raise IngestionError("CAMARA_SESSION_START_DATE_MISMATCH")
    return {
        "starts_at": start.isoformat(),
        "description": session.findtext("descricao"),
        "presence_status": presence_state(session.findtext("frequencia")),
    }
