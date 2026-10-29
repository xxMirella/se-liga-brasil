"""Rebuild the dated 1992-1994 Senate snapshots from archived official sources (no network).

Inputs: the documentary inventory of the Itamar-period Senate (official API payloads, roll
calls, Anais headings) and the Zucco and Power 2024 supplement (Table C1). Occupants are
chosen by the explicit seat table below; party labels are never inferred from names.
"""

import datetime as dt
import hashlib
import json
from pathlib import Path

INVENTORY = Path("data/political-orientation/itamar-senate-inventory-1992-1994.json")
OUTPUT = Path("src/service/political_dashboard/senate_orientation_1992_1994.json")
SNAPSHOT_DATES = ("1992-12-31", "1993-12-31", "1994-12-31")
VOTE_WINDOW_DAYS = 120
KNOWN_LABELS = {
    "PMDB": "MDB",
    "MDB": "MDB",
    "PFL": "PFL",
    "PSDB": "PSDB",
    "PDT": "PDT",
    "PT": "PT",
    "PTB": "PTB",
    "PSB": "PSB",
    "PDS": "PDS",
    "PPR": "PPR",
    "PP": "PP",
    "PRN": "PRN",
    "PDC": "PDC",
    "S/Partido": "S/Partido",
}
# role: T titular; S suplente em exercício; R retorno provável do titular (licença
# ministerial encerrada, retomada não comprovada); A ocupante ambíguo (titular ou suplente).
SEATS = [
    ("AC", "Aluízio Bezerra", ("222:T", "222:T", "222:T")),
    ("AC", "Flaviano Melo", ("24:T", "24:T", "24:T")),
    ("AC", "Nabor Júnior", ("62:T", "62:T", "62:T")),
    ("AL", "Divaldo Suruagy", ("1581:T", "1581:T", "1581:T")),
    ("AL", "Guilherme Palmeira", ("31:T", "31:T", "31:T")),
    ("AL", "Teotonio Vilela Filho", ("78:T", "78:T", "78:T")),
    ("AM", "Amazonino Mendes", ("29:S", "29:S", "29:S")),
    ("AM", "Fábio Lucena", ("1503:S", "1503:S", "1503:S")),
    ("AM", "Carlos De' Carli", ("1537:T", "1537:T", "1537:T")),
    ("AP", "Henrique Almeida", ("1737:T", "1737:T", "1737:A")),
    ("AP", "Jonas Pinheiro", ("1869:T", "1869:T", "1869:T")),
    ("AP", "José Sarney", ("47:T", "47:T", "47:T")),
    ("BA", "Josaphat Marinho", ("39:T", "39:T", "39:T")),
    ("BA", "Jutahy Magalhães", ("1999:T", "1999:T", "1999:T")),
    ("BA", "Ruy Bacelar", ("1864:T", "1864:T", "1864:T")),
    ("CE", "Beni Veras", ("8:T", "8:T", "139:S")),
    ("CE", "Cid Sabóia de Carvalho", ("1562:T", "1562:T", "1562:T")),
    ("CE", "Mauro Benevides", ("1244:T", "1244:T", "1244:T")),
    ("DF", "Maurício Corrêa", ("2190:S", "2190:S", "2117:T")),
    ("DF", "Meira Filho", ("1781:T", "1781:T", "1781:T")),
    ("DF", "Valmir Campelo", ("79:T", "79:T", "79:T")),
    ("ES", "Elcio Alvares", ("18:T", "18:T", "161:S")),
    ("ES", "Gerson Camata", ("28:T", "28:T", "3272:S")),
    ("ES", "João Calmon", ("1799:T", "1799:T", "1799:T")),
    ("GO", "Iram Saraiva", ("1748:T", "1748:T", "2937:S")),
    ("GO", "Irapuan Costa Júnior", ("1749:T", "1749:T", "1749:T")),
    ("GO", "Onofre Quinan", ("65:T", "65:T", "65:T")),
    ("MA", "Alexandre Costa", ("185:S", "2:R", "2:T")),
    ("MA", "Edison Lobão", ("1552:S", "1552:S", "1552:S")),
    ("MA", "Epitácio Cafeteira", ("20:T", "20:T", "20:T")),
    ("MG", "Alfredo Campos", ("1383:T", "1383:T", "1383:T")),
    ("MG", "Junia Marise", ("51:T", "51:T", "51:T")),
    ("MG", "Ronan Tito", ("2224:T", "2224:T", "2224:T")),
    ("MS", "Saldanha Derzi", ("2203:T", "2203:T", "2203:T")),
    ("MS", "Levy Dias", ("54:T", "54:T", "54:T")),
    ("MS", "Wilson Martins", ("2282:T", "2282:T", "2282:T")),
    ("MT", "Júlio Campos", ("50:T", "50:T", "50:T")),
    ("MT", "Louremberg Nunes", ("2017:T", "2017:T", "2017:T")),
    ("MT", "Márcio Lacerda", ("1952:T", "1952:T", "1952:T")),
    ("PA", "Almir Gabriel", ("1387:T", "1387:T", "1387:T")),
    ("PA", "Coutinho Jorge", ("136:S", "14:T", "14:T")),
    ("PA", "Jarbas Passarinho", ("1764:T", "1764:T", "1764:T")),
    ("PB", "Antonio Mariz", ("84:T", "84:T", "84:T")),
    ("PB", "Humberto Lucena", ("33:T", "33:T", "33:T")),
    ("PB", "Raimundo Lira", ("2207:T", "2207:T", "2207:T")),
    ("PE", "Mansueto de Lavor", ("2194:T", "2194:T", "2194:T")),
    ("PE", "Marco Maciel", ("86:T", "86:T", "86:T")),
    ("PE", "Antônio Farias", ("2144:S", "2144:S", "2144:S")),
    ("PI", "Chagas Rodrigues", ("1657:T", "1657:T", "1657:T")),
    ("PI", "Hugo Napoleão", ("1398:S", "32:R", "32:T")),
    ("PI", "Lucídio Portella", ("55:T", "55:T", "55:T")),
    ("PR", "Affonso Camargo", ("346:T", "346:T", "346:T")),
    ("PR", "José Eduardo", ("56:S", "85:R", "85:T")),
    ("PR", "José Richa", ("1974:T", "1974:T", "1974:T")),
    ("RJ", "Darcy Ribeiro", ("15:T", "15:T", "15:T")),
    ("RJ", "Nelson Carneiro", ("2137:T", "2137:T", "2137:T")),
    ("RJ", "Affonso Arinos", ("1746:S", "1746:S", "1746:S")),
    ("RN", "Garibaldi Alves Filho", ("87:T", "87:T", "87:T")),
    ("RN", "Lavoisier Maia", ("799:T", "799:T", "799:T")),
    ("RN", "José Agripino", ("1572:S", "1572:S", "1572:S")),
    ("RO", "Odacir Soares", ("64:T", "64:T", "64:T")),
    ("RO", "Ronaldo Aragão", ("1978:T", "1978:T", "1978:T")),
    ("RO", "Amir Lando", ("1025:T", "1025:T", "1025:T")),
    ("RR", "César Dias", ("88:T", "88:T", "88:T")),
    ("RR", "Marluce Pinto", ("60:T", "60:T", "60:T")),
    ("RR", "Hélio Campos", ("48:S", "48:S", "48:S")),
    ("RS", "José Fogaça", ("44:T", "44:T", "44:T")),
    ("RS", "Paulo Bisol", ("1967:T", "1967:T", "1967:T")),
    ("RS", "Pedro Simon", ("68:T", "68:T", "68:T")),
    ("SC", "Dirceu Carneiro", ("1579:T", "1579:T", "1579:T")),
    ("SC", "Esperidião Amin", ("22:T", "22:T", "22:T")),
    ("SC", "Nelson Wedekin", ("2139:T", "2139:T", "2139:T")),
    ("SE", "Albano Franco", ("89:T", "89:T", "89:T")),
    ("SE", "Francisco Rollemberg", ("1687:T", "1687:T", "1687:T")),
    ("SE", "Lourival Baptista", ("2019:T", "2019:T", "2019:T")),
    ("SP", "Eduardo Suplicy", ("17:T", "17:T", "17:T")),
    ("SP", "Mário Covas", ("2108:T", "2108:T", "2108:T")),
    ("SP", "Fernando Henrique Cardoso", ("1618:S", "1618:S", "1634:R")),
    ("TO", "Carlos Patrocínio", ("11:T", "11:T", "11:T")),
    ("TO", "João Rocha", ("49:T", "49:T", "49:T")),
    ("TO", "Moisés Abrão", ("2131:T", "2131:T", "2131:T")),
]
ROLE_LABELS = {
    "T": "titular",
    "S": "suplente_em_exercicio",
    "R": "titular_retorno_provavel_nao_comprovado",
    "A": "ocupante_ambiguo_titular_ou_suplente",
}
AMBIGUOUS_ALTERNATIVE = {("AP", "1994-12-31"): "3233"}
# Party leadership listing printed in the Diário do Congresso Nacional of 12/04/1994
# (Anais 1994, book 6, OCR lines 14184-14224). Only party-bound posts are transcribed; the
# Mesa block of the same page is stale (elected in 1993) and is deliberately ignored.
LEADERSHIP_LISTING_DATE = "1994-04-12"
LEADERSHIP_LISTING = {
    "1978": "PMDB",
    "2194": "PMDB",
    "2108": "PSDB",
    "1999": "PSDB",
    "2131": "PPR",
    "1552": "PDT",
    "2144": "PRN",
    "1503": "PRN",
    "1749": "PP",
    "20": "PPR",
    "346": "PPR",
    "22": "PPR",
}
HEADING_ANAIS = {
    "1992": "anais-1992-book-20",
    "1993": "anais-1993-book-4",
    "1994": "anais-1994-book-6",
}


def day(value):
    return dt.date.fromisoformat(value)


def load_people():
    inventory = json.loads(INVENTORY.read_text())
    people = {row["source_person_id"]: row for row in inventory["people"]}
    headings = {}
    for annual in inventory["annual_inventory"]:
        for row in annual["rows"]:
            headings[(row["source_person_id"], str(annual["year"]))] = [
                KNOWN_LABELS[label]
                for label in row["printed_heading_party_labels"]
                if label in KNOWN_LABELS
            ]
    return people, headings


def affiliation_claim(person, snapshot):
    covering = [
        row
        for row in person["affiliation_intervals"]
        if row["starts_on"] <= snapshot <= (row["ends_on"] or "9999-12-31")
    ]
    labels = {KNOWN_LABELS.get(row["source_abbreviation"]) for row in covering}
    if len(labels) != 1 or None in labels:
        return None
    row = covering[0]
    return {
        "raw_label": row["source_abbreviation"],
        "party_key": labels.pop(),
        "source_kind": "senate_api_affiliation_interval",
        "source_url": row["source_url"],
        "valid_from": row["starts_on"],
        "valid_until_inclusive": row["ends_on"],
    }


def nearest_vote_claim(person, snapshot, window=150):
    target = day(snapshot)
    candidates = []
    for vote in person["rollcall_observations"]:
        label = KNOWN_LABELS.get(vote["source_party_abbreviation"])
        gap = abs((day(vote["observed_on"]) - target).days)
        if label and gap <= window:
            candidates.append((gap, vote, label))
    if not candidates:
        return None
    gap, vote, label = min(candidates, key=lambda item: item[0])
    return {
        "raw_label": vote["source_party_abbreviation"],
        "party_key": label,
        "source_kind": "senate_api_nominal_vote_party_label",
        "observed_on": vote["observed_on"],
        "days_from_snapshot": gap,
        "source_url": vote["source_url"],
    }


def heading_claim(person_id, snapshot, headings):
    labels = set(headings.get((person_id, snapshot[:4]), []))
    if len(labels) != 1:
        return None
    label = labels.pop()
    return {
        "raw_label": label,
        "party_key": label,
        "source_kind": "printed_anais_heading_same_year",
        "source_document": HEADING_ANAIS[snapshot[:4]],
    }


def leadership_claim(person_id, snapshot):
    label = LEADERSHIP_LISTING.get(person_id)
    if not label or snapshot != SNAPSHOT_DATES[-1]:
        return None
    return {
        "raw_label": label,
        "party_key": KNOWN_LABELS.get(label, label),
        "source_kind": "printed_diario_party_leadership_listing",
        "observed_on": LEADERSHIP_LISTING_DATE,
        "days_from_snapshot": (day(snapshot) - day(LEADERSHIP_LISTING_DATE)).days,
        "source_document": HEADING_ANAIS["1994"],
    }


def resolve_party(person, snapshot, headings):
    for claim in (
        affiliation_claim(person, snapshot),
        nearest_vote_claim(person, snapshot),
        leadership_claim(person["source_person_id"], snapshot),
        heading_claim(person["source_person_id"], snapshot, headings),
    ):
        if claim:
            return claim
    return {"raw_label": None, "party_key": None, "source_kind": "gap_no_party_claim_for_date"}


def vote_observed_near(person, snapshot):
    target = day(snapshot)
    return any(
        abs((day(v["observed_on"]) - target).days) <= VOTE_WINDOW_DAYS
        for v in person["rollcall_observations"]
    )


def seat_record(uf, seat, specification, snapshot, people, headings):
    person_id, role = specification.split(":")
    person = people[person_id]
    record = {
        "uf": uf,
        "seat": seat,
        "occupant_source_id": person_id,
        "occupant_name": person["name"],
        "occupant_role": ROLE_LABELS[role],
        "nominal_vote_within_120_days": vote_observed_near(person, snapshot),
        "party": resolve_party(person, snapshot, headings),
    }
    alternative = AMBIGUOUS_ALTERNATIVE.get((uf, snapshot))
    if role == "A" and alternative:
        other = people[alternative]
        record["alternative_occupant"] = {
            "source_id": alternative,
            "name": other["name"],
            "party": resolve_party(other, snapshot, headings),
        }
    return record


def build_snapshots(people, headings):
    snapshots = []
    for index, snapshot in enumerate(SNAPSHOT_DATES):
        seats = [
            seat_record(uf, seat, roles[index], snapshot, people, headings)
            for uf, seat, roles in SEATS
        ]
        snapshots.append({"snapshot_on": snapshot, "seats": seats})
    return snapshots


def main():
    people, headings = load_people()
    target = json.loads(OUTPUT.read_text()) if OUTPUT.exists() else {}
    target["snapshots"] = build_snapshots(people, headings)
    target["inventory_sha256"] = hashlib.sha256(INVENTORY.read_bytes()).hexdigest()
    OUTPUT.write_text(json.dumps(target, ensure_ascii=False, indent=1) + "\n")


if __name__ == "__main__":
    main()
