"""Reconcile dated REST affiliations with identity-checked legacy exercise periods."""

import hashlib
import json
from datetime import datetime
from urllib.parse import parse_qs, urlparse
from xml.etree import ElementTree

from crawlers.camara.legacy_exercises import LEGACY_ENDPOINT, legacy_period_covers_day


def load_legacy_reconciliation(storage):
    records = {}
    for manifest in sorted(storage.glob("legacy-*/sources.json")):
        for evidence in json.loads(manifest.read_text()):
            if evidence.get("http_status") != 200:
                continue
            key, record = verified_legacy_record(manifest.parent, evidence)
            if key in records:
                raise ValueError("CHAMBER_RECONCILIATION_DUPLICATE_SOURCE")
            records[key] = record
    attach_reviewed_rest_conflicts(storage, records)
    return records


def legacy_exercise_period(row):
    return {"starts_on": datetime.strptime(row.findtext("dataInicio"), "%d/%m/%Y").date(),
            "ends_on": datetime.strptime(row.findtext("dataFim"), "%d/%m/%Y").date()
            if str(row.findtext("dataFim") or "").strip() else None,
            "uf": row.findtext("siglaUFRepresentacao"),
            "legacy_exercise_condition": row.findtext("situacaoExercicio"),
            "previous_source_person_id": row.findtext("idCadastroParlamentarAnterior"),
            "end_cause": row.findtext("descricaoCausaFimExercicio")}


def latest_affiliation_group(events, legislature, bounds, reference):
    candidates = [event for event in events if event.get("idLegislatura") == legislature
                  and event.get("situacao")
                  and bounds["dataInicio"][:10] <= event["dataHora"][:10] <= reference]
    if not candidates:
        return []
    observed = max(event["dataHora"] for event in candidates)
    return [event for event in candidates if event["dataHora"] == observed]


def corroborated_historical_member(history, records, legislatures, year):
    reference = datetime(year, 12, 31).date()
    accepted = []
    for legislature, bounds in legislatures.items():
        record = records.get((history["official_deputy_id"], legislature))
        if record is None:
            continue
        if not bounds["dataInicio"][:10] <= str(reference) <= bounds["dataFim"][:10]:
            continue
        group = latest_affiliation_group(history["events"], legislature, bounds, str(reference))
        if not corroboratable_rest_group(record, group, year):
            continue
        periods = [row for row in record["periods"]
                   if legacy_period_covers_day(row, reference, record.get("observed_through"))]
        if len(periods) != 1:
            continue
        if periods[0]["uf"] != group[0]["siglaUf"]:
            raise ValueError("CHAMBER_RECONCILIATION_TERRITORY_CONFLICT")
        accepted.append((group, periods[0], record["evidence"]))
    if len(accepted) > 1:
        raise ValueError("CHAMBER_RECONCILIATION_OVERLAPPING_LEGISLATURES")
    return accepted[0] if accepted else None


def reviewed_rest_conflict(record, group, year):
    signatures = {(row["situacao"], row["dataHora"], row.get("siglaPartido"),
                   row.get("siglaUf")) for row in group}
    return any(review["year"] == year and signatures == {(
        review["rest_status"], review["rest_recorded_at"], review["political_party"], review["uf"]
    )} for review in record.get("reviewed_rest_conflicts", []))


def attach_reviewed_rest_conflicts(storage, records):
    path = storage / "reviewed-rest-conflicts.json"
    if not path.exists():
        return
    for review in json.loads(path.read_text()):
        identifier = review["source_person_id"]
        evidence = review["biography_evidence"]
        if evidence["url"] != f"https://www.camara.leg.br/deputados/{identifier}/biografia":
            raise ValueError("CHAMBER_REVIEWED_BIOGRAPHY_IDENTITY_MISMATCH")
        raw = (storage / "reviewed-evidence" / (evidence["sha256"] + ".html")).read_bytes()
        if hashlib.sha256(raw).hexdigest() != evidence["sha256"]:
            raise ValueError("CHAMBER_REVIEWED_BIOGRAPHY_HASH_MISMATCH")
        records[(identifier, review["legislature"])].setdefault(
            "reviewed_rest_conflicts", [],
        ).append(review)



def verified_legacy_record(directory, evidence):
    url = evidence["url"]
    if not url.startswith(LEGACY_ENDPOINT + "?"):
        raise ValueError("CHAMBER_RECONCILIATION_UNEXPECTED_SOURCE")
    raw = (directory / (evidence["sha256"] + ".xml")).read_bytes()
    if hashlib.sha256(raw).hexdigest() != evidence["sha256"]:
        raise ValueError("CHAMBER_RECONCILIATION_HASH_MISMATCH")
    deputy = ElementTree.fromstring(raw).find("Deputado")
    parameters = parse_qs(urlparse(url).query)
    identifier = deputy.findtext("ideCadastro")
    legislature = deputy.findtext("numLegislatura")
    if ([identifier] != parameters.get("ideCadastro")
            or [legislature] != parameters.get("numLegislatura")):
        raise ValueError("CHAMBER_RECONCILIATION_IDENTITY_MISMATCH")
    record = {"evidence": evidence, "name": deputy.findtext("nomeCivil"),
              "observed_through": datetime.fromisoformat(evidence["fetched_at"]).date(),
              "periods": [legacy_exercise_period(row) for row in
                          deputy.findall("periodosExercicio/periodoExercicio")]}
    return (identifier, int(legislature)), record



def corroboratable_rest_group(record, group, year):
    signatures = {(row.get("siglaPartido"), row.get("siglaUf")) for row in group}
    if len(signatures) != 1 or not group[0].get("siglaPartido"):
        return False
    administrative = all(row["situacao"] in {"CONVOCADO", "Exercício"} for row in group)
    return administrative or reviewed_rest_conflict(record, group, year)
