"""Corroborate ambiguous REST entries using archived official legacy exercise intervals."""

import hashlib
import json
from datetime import datetime
from urllib.parse import parse_qs, urlparse
from xml.etree import ElementTree

from crawlers.camara.historical_exercises import latest_unambiguous_status

LEGACY_ENDPOINT = "https://www.camara.leg.br/SitCamaraWS/Deputados.asmx/ObterDetalhesDeputado"


def read_verified_legacy_periods(storage):
    periods = {}
    for evidence in json.loads((storage / "sources.json").read_text()):
        url = evidence["url"]
        if not url.startswith(LEGACY_ENDPOINT + "?") or evidence.get("http_status") != 200:
            continue
        content = (storage / (evidence["sha256"] + ".xml")).read_bytes()
        if hashlib.sha256(content).hexdigest() != evidence["sha256"]:
            raise ValueError("CHAMBER_LEGACY_SOURCE_HASH_MISMATCH")
        deputy = ElementTree.fromstring(content).find("Deputado")
        parameters = parse_qs(urlparse(url).query)
        identifier = deputy.findtext("ideCadastro")
        legislature = deputy.findtext("numLegislatura")
        if ([identifier] != parameters.get("ideCadastro")
                or [legislature] != parameters.get("numLegislatura")):
            raise ValueError("CHAMBER_LEGACY_IDENTITY_MISMATCH")
        periods[identifier] = {"legislature": int(legislature), "evidence": evidence,
                               "observed_through": datetime.fromisoformat(
                                   evidence["fetched_at"],
                               ).date(),
                               "periods": [parse_exercise_period(row) for row in
                                           deputy.findall("periodosExercicio/periodoExercicio")]}
    return periods


def parse_exercise_period(row):
    return {"starts_on": datetime.strptime(row.findtext("dataInicio"), "%d/%m/%Y").date(),
            "ends_on": datetime.strptime(row.findtext("dataFim"), "%d/%m/%Y").date()
            if str(row.findtext("dataFim") or "").strip() else None,
            "uf": row.findtext("siglaUFRepresentacao")}


def corroborated_legacy_entry(history, record, year):
    reference = datetime(year, 12, 31, 23, 59, 59)
    # End dates have day precision. Never resolve an end-of-day boundary by assumption.
    periods = [row for row in record["periods"]
               if legacy_period_covers_day(row, reference.date(), record.get("observed_through"))]
    if len(periods) != 1:
        return None
    status = latest_unambiguous_status(history["events"], record["legislature"],
                                       datetime(year - 4, 1, 1), reference)
    if not status or status.get("situacao") != "CONVOCADO":
        return None
    if not str(status.get("descricaoStatus", "")).startswith("Entrada - Reassunção"):
        return None
    if status.get("siglaUf") != periods[0]["uf"]:
        raise ValueError("CHAMBER_LEGACY_REST_TERRITORY_CONFLICT")
    return status



def legacy_period_covers_day(period, reference, observed_through=None):
    if reference < period["starts_on"]:
        return False
    if period["ends_on"] is not None:
        return reference < period["ends_on"]
    return observed_through is not None and reference <= observed_through
