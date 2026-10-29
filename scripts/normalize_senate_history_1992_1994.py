"""Normalize the archived Senate open-data responses for the 1992-1994 occupants.

Reads only the local archive (no network, no database). Affiliation ends are
converted from the API's inclusive last day to an exclusive bound. Nothing is
inferred by name; absent data stays absent. Also compares the result with the
dated inventory snapshots.
"""

import json
from datetime import date, timedelta
from pathlib import Path

SOURCE_DIRECTORY = Path("data/political-dashboard/senate-history-1992-1994-source")
INVENTORY_PATH = Path("src/service/political_dashboard/senate_orientation_1992_1994.json")
NORMALIZED_PATH = Path("data/political-dashboard/senate-history-1992-1994-normalized.json")
RESEARCH_INVENTORY_PATH = Path("data/political-orientation/itamar-senate-inventory-1992-1994.json")
COMPARISON_PATH = Path(
    "data/political-dashboard/senate-history-1992-1994-inventory-comparison.json"
)


def as_list(value) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def exclusive_end(inclusive_end: str | None) -> str | None:
    if not inclusive_end:
        return None
    return (date.fromisoformat(inclusive_end) + timedelta(days=1)).isoformat()


def load_manifest() -> dict[tuple[str, str | None], dict]:
    entries = json.loads((SOURCE_DIRECTORY / "manifest.json").read_text(encoding="utf-8"))
    return {(entry["kind"], entry["senator_id"]): entry for entry in entries}


def read_payload(
    manifest: dict, kind: str, senator_id: str | None
) -> tuple[dict | None, dict | None]:
    entry = manifest.get((kind, senator_id))
    if entry is None or entry["http_status"] != 200 or entry["bytes"] == 0:
        return None, entry
    return json.loads((SOURCE_DIRECTORY / entry["path"]).read_bytes()), entry


def source_reference(entry: dict | None) -> dict | None:
    if entry is None:
        return None
    return {"url": entry["url"], "sha256": entry["sha256"], "http_status": entry["http_status"]}


def normalize_affiliation(raw: dict, reference: dict | None) -> dict:
    party = raw.get("Partido", {})
    return {
        "party_code": party.get("CodigoPartido"),
        "party_acronym": party.get("SiglaPartido"),
        "party_name": party.get("NomePartido"),
        "valid_from": raw.get("DataFiliacao") or None,
        "valid_until_exclusive": exclusive_end(raw.get("DataDesfiliacao")),
        "valid_until_inclusive_source": raw.get("DataDesfiliacao") or None,
        "source": reference,
    }


def normalize_affiliations(payload: dict | None, reference: dict | None) -> list[dict]:
    if payload is None:
        return []
    block = payload["FiliacaoParlamentar"]["Parlamentar"].get("Filiacoes") or {}
    return [normalize_affiliation(raw, reference) for raw in as_list(block.get("Filiacao"))]


def normalize_exercise(raw: dict) -> dict:
    return {
        "exercise_code": raw.get("CodigoExercicio"),
        "starts_on": raw.get("DataInicio"),
        "ends_on_inclusive": raw.get("DataFim"),
        "ends_on_exclusive": exclusive_end(raw.get("DataFim")),
        "leave_cause_code": (raw.get("SiglaCausaAfastamento") or "").strip() or None,
        "leave_cause": raw.get("DescricaoCausaAfastamento"),
    }


def normalize_mandate(raw: dict) -> dict:
    first = raw.get("PrimeiraLegislaturaDoMandato", {})
    second = raw.get("SegundaLegislaturaDoMandato", {})
    titular = raw.get("Titular") or {}
    return {
        "mandate_code": raw.get("CodigoMandato"),
        "uf": raw.get("UfParlamentar"),
        "participation": raw.get("DescricaoParticipacao"),
        "titular_senator_id": titular.get("CodigoParlamentar"),
        "legislatures": [first.get("NumeroLegislatura"), second.get("NumeroLegislatura")],
        "starts_on": first.get("DataInicio"),
        "ends_on_inclusive": second.get("DataFim"),
        "ends_on_exclusive": exclusive_end(second.get("DataFim")),
        "exercises": [
            normalize_exercise(e) for e in as_list((raw.get("Exercicios") or {}).get("Exercicio"))
        ],
        "embedded_parties": [
            {
                "party_code": p.get("CodigoPartido"),
                "party_acronym": p.get("Sigla"),
                "party_name": p.get("Nome"),
                "valid_from": p.get("DataFiliacao"),
                "valid_until_inclusive_source": p.get("DataDesfiliacao"),
            }
            for p in as_list((raw.get("Partidos") or {}).get("Partido"))
        ],
    }


def normalize_mandates(payload: dict | None) -> list[dict]:
    if payload is None:
        return []
    block = payload["MandatoParlamentar"]["Parlamentar"].get("Mandatos") or {}
    return [normalize_mandate(raw) for raw in as_list(block.get("Mandato"))]


def normalize_identity(payload: dict | None) -> dict:
    if payload is None:
        return {}
    parliamentarian = payload["DetalheParlamentar"]["Parlamentar"]
    identification = parliamentarian["IdentificacaoParlamentar"]
    basic = parliamentarian.get("DadosBasicosParlamentar", {})
    return {
        "parliamentary_name": identification.get("NomeParlamentar"),
        "civil_name": identification.get("NomeCompletoParlamentar"),
        "birth_date": basic.get("DataNascimento"),
        "death_date": basic.get("DataFalecimento"),
        "home_uf": basic.get("UfNaturalidade"),
    }


def normalize_leaves(payload: dict | None) -> list[dict]:
    if payload is None:
        return []
    block = payload["LicencaParlamentar"]["Parlamentar"].get("Licencas") or {}
    return as_list(block.get("Licenca"))


def normalize_senator(senator_id: str, inventory_name: str, manifest: dict) -> dict:
    detail, detail_entry = read_payload(manifest, "detail", senator_id)
    mandates, mandates_entry = read_payload(manifest, "mandates", senator_id)
    affiliations, affiliations_entry = read_payload(manifest, "affiliations", senator_id)
    leaves, leaves_entry = read_payload(manifest, "leaves", senator_id)
    return {
        "senate_id": senator_id,
        "inventory_name": inventory_name,
        **normalize_identity(detail),
        "mandates": normalize_mandates(mandates),
        "affiliations": normalize_affiliations(affiliations, source_reference(affiliations_entry)),
        "leaves": normalize_leaves(leaves),
        "sources": {
            "detail": source_reference(detail_entry),
            "mandates": source_reference(mandates_entry),
            "affiliations": source_reference(affiliations_entry),
            "leaves": source_reference(leaves_entry),
        },
    }


def historical_parties(senators: list[dict], manifest: dict) -> list[dict]:
    payload, entry = read_payload(manifest, "parties", None)
    catalog = (
        {p["Codigo"]: p for p in as_list(payload["ListaPartidos"]["Partidos"]["Partido"])}
        if payload
        else {}
    )
    found: dict[tuple, dict] = {}
    for senator in senators:
        for item in senator["affiliations"]:
            found.setdefault((item["party_code"], item["party_acronym"]), item)
    parties = []
    for (code, acronym), item in sorted(found.items(), key=lambda kv: str(kv[0])):
        listed = catalog.get(code, {})  # matched by code only, never by acronym or name
        parties.append(
            {
                "acronym": acronym,
                "name_in_affiliation": item["party_name"],
                "affiliation_party_code": code,
                "catalog_code": listed.get("Codigo"),
                "catalog_name": listed.get("Nome"),
                "created_on": listed.get("DataCriacao"),
                "extinguished_on": listed.get("DataExtincao"),
                "in_catalog": bool(listed),
                "succession": None,
            }
        )
    return parties


def inventory_people() -> dict[str, str]:
    inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    people = {
        seat["occupant_source_id"]: seat["occupant_name"]
        for snap in inventory["snapshots"]
        for seat in snap["seats"]
    }
    research = json.loads(RESEARCH_INVENTORY_PATH.read_text(encoding="utf-8"))
    for person in research["people"]:
        people.setdefault(person["source_person_id"], person["name"])
    return people


def covering(senator: dict, on: str) -> list[dict]:
    """Affiliations whose dated interval contains `on`; undated ones never cover."""
    return [
        a
        for a in senator["affiliations"]
        if a["valid_from"]
        and a["party_acronym"]
        and a["valid_from"] <= on
        and (a["valid_until_exclusive"] is None or on < a["valid_until_exclusive"])
    ]


def compare_seat(seat: dict, senator: dict, on: str) -> dict:
    claimed = seat["party"].get("party_key")
    api = sorted({a["party_acronym"] for a in covering(senator, on)})
    if not api:
        status = "api_no_interval"
    elif claimed is None:
        status = "api_resolves_inventory_gap"
    elif claimed in api:
        status = "agrees"
    else:
        status = "conflict"
    return {
        "date": on,
        "senate_id": seat["occupant_source_id"],
        "name": seat["occupant_name"],
        "uf": seat["uf"],
        "inventory_party": claimed,
        "inventory_source_kind": seat["party"].get("source_kind"),
        "api_parties": api,
        "status": status,
    }


def snapshot_occupant_ids() -> set[str]:
    inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    return {seat["occupant_source_id"] for snap in inventory["snapshots"] for seat in snap["seats"]}


def compare_inventory(senators_by_id: dict[str, dict]) -> list[dict]:
    inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    return [
        compare_seat(seat, senators_by_id[seat["occupant_source_id"]], snap["snapshot_on"])
        for snap in inventory["snapshots"]
        for seat in snap["seats"]
    ]


def main() -> None:
    manifest = load_manifest()
    people = inventory_people()
    occupants = snapshot_occupant_ids()
    senators = [
        normalize_senator(i, name, manifest)
        for i, name in sorted(people.items(), key=lambda kv: int(kv[0]))
    ]
    for senator in senators:
        senator["in_snapshots"] = senator["senate_id"] in occupants
    NORMALIZED_PATH.write_text(
        json.dumps(
            {
                "schema_version": "senate_history_1992_1994.v1",
                "note": "Valid-until bounds are exclusive (API inclusive last day + 1). "
                "Absence in a response does not prove departure.",
                "snapshot_occupant_count": len(occupants),
                "senator_count": len(senators),
                "senators": senators,
                "historical_parties": historical_parties(senators, manifest),
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    comparison = compare_inventory({s["senate_id"]: s for s in senators})
    COMPARISON_PATH.write_text(
        json.dumps(comparison, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"{len(senators)} senators, {len(comparison)} seat-dates")


if __name__ == "__main__":
    main()
