"""PostgreSQL adapter for the 1992-1994 Senate history load.

One set-based statement per table, all idempotent and all returning the rows really inserted.
The adapter never opens or ends a transaction: the caller owns commit and rollback.
"""

import re
from collections import Counter
from dataclasses import dataclass, field
from functools import cache

from psycopg.pq import TransactionStatus
from psycopg.types.json import Jsonb

from crawlers.senado.configuration import SOURCE
from crawlers.senado.historical_period_contracts import (
    AFFILIATION_SCOPE,
    LOAD_NAME,
    SENATE_PARTY_CODE_PREFIX,
    LoadPlan,
    PendingItem,
    SenatorBundle,
)
from crawlers.senado.historical_period_rows import (
    affiliation_key,
    affiliation_record,
    bundle_documents,
    date_text,
    document_record,
    name_birth_row,
    party_record,
    person_id_for,
    qualified_abbreviation,
    term_key,
)
from database.operations import read_sql_file
from service.ingestion.contracts import IngestionError

STATEMENT_MARKER = re.compile(r"(?m)^-- statement: (\w+)\s*$")
TABLES = (
    "source",
    "institution",
    "source_record",
    "political_party",
    "person",
    "person_identifier",
    "office_term",
    "office_exercise",
    "political_party_affiliation",
    "person_fact",
)


@cache
def named_statements() -> dict[str, str]:
    text = read_sql_file("ingestion/senado_historical_period.sql")
    parts = STATEMENT_MARKER.split(text)
    return {
        name: sql.strip().rstrip(";") for name, sql in zip(parts[1::2], parts[2::2], strict=True)
    }


@dataclass
class WriteOutcome:
    inserted: Counter = field(default_factory=Counter)
    conflicts: list[dict] = field(default_factory=list)
    review_required: list[PendingItem] = field(default_factory=list)
    senators_written: int = 0
    senators_linked_to_existing_identity: int = 0
    party_abbreviations: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class AcceptedSenator:
    bundle: SenatorBundle
    person_id: str
    has_identifier: bool
    creates_person: bool = False


class HistoricalSenateWriter:
    def __init__(self, connection, reviewed_links: dict[str, str] | None = None) -> None:
        """reviewed_links maps a Senate ID to a person a human approved after a name+birth match."""
        self.connection = connection
        self.statements = named_statements()
        self.reviewed_links = reviewed_links or {}

    def write(self, plan: LoadPlan) -> WriteOutcome:
        if self.connection.info.transaction_status == TransactionStatus.IDLE:
            raise IngestionError("TRANSACTION_REQUIRED_FOR_HISTORICAL_LOAD")
        outcome = WriteOutcome()
        self._prepare_session()
        source_id, institution_id = self._ensure_references(outcome)
        accepted = self._resolve_identities(plan, source_id, outcome)
        record_ids = self._store_source_records(plan, accepted, source_id, outcome)
        self._store_parties(plan, accepted, record_ids, outcome)
        self._store_people(accepted, source_id, record_ids, outcome)
        self._store_terms_and_exercises(accepted, institution_id, record_ids, outcome)
        self._store_affiliations(accepted, record_ids, outcome)
        self._store_facts(accepted, record_ids, outcome)
        outcome.senators_written = len(accepted)
        return outcome

    def _prepare_session(self) -> None:
        self.connection.execute("SET LOCAL lock_timeout='10s'")
        self.connection.execute("SET LOCAL statement_timeout='120s'")
        self.connection.execute(
            "SELECT pg_advisory_xact_lock(hashtext('se_liga_brasil:senate_history_1992_1994'))"
        )

    def _run(self, name: str, parameters: dict) -> list:
        prepared = {
            key: Jsonb(value) if key == "rows" else value for key, value in parameters.items()
        }
        return self.connection.execute(self.statements[name], prepared).fetchall()

    def _ensure_references(self, outcome: WriteOutcome) -> tuple[int, int]:
        inserted = self._run(
            "ensure_source",
            {
                "source_code": SOURCE.code,
                "publisher": SOURCE.publisher,
                "official_url": SOURCE.official_url,
            },
        )
        outcome.inserted["source"] += len(inserted)
        outcome.inserted["institution"] += len(self._run("ensure_institution", {}))
        source_id = self.connection.execute(
            "SELECT id FROM se_liga_brasil.source WHERE code=%s", (SOURCE.code,)
        ).fetchone()["id"]
        institution_id = self.connection.execute(
            "SELECT id FROM se_liga_brasil.institution WHERE code='senado'"
        ).fetchone()["id"]
        return source_id, institution_id

    def _resolve_identities(self, plan, source_id, outcome) -> list[AcceptedSenator]:
        senator_ids = [bundle.identity.senator_id for bundle in plan.senators]
        existing = {
            row["external_id"]: row
            for row in self._run(
                "select_existing_identities",
                {"source_id": source_id, "senator_ids": senator_ids},
            )
        }
        unlinked = [b for b in plan.senators if b.identity.senator_id not in existing]
        homonyms = self._name_and_birth_matches(unlinked)
        accepted = []
        for bundle in plan.senators:
            senator_id = bundle.identity.senator_id
            decision = self._identity_decision(
                bundle, existing.get(senator_id), homonyms.get(senator_id, [])
            )
            if isinstance(decision, PendingItem):
                outcome.review_required.append(decision)
                continue
            accepted.append(decision)
            outcome.senators_linked_to_existing_identity += 0 if decision.creates_person else 1
        return accepted

    def _identity_decision(self, bundle, existing_row, homonyms) -> "AcceptedSenator | PendingItem":
        """Official ID first; a name+birth match is never linked without a human decision."""
        senator_id = bundle.identity.senator_id
        if existing_row and existing_row["is_alias"]:
            return _review("IDENTITY_IS_MERGED_ALIAS", senator_id)
        if existing_row:
            return AcceptedSenator(bundle, existing_row["person_id"], True)
        if homonyms and self.reviewed_links.get(senator_id) == homonyms[0] and len(homonyms) == 1:
            return AcceptedSenator(bundle, homonyms[0], False)
        if homonyms:
            return _review("IDENTITY_REVIEW_REQUIRED", senator_id, ",".join(sorted(homonyms)))
        return AcceptedSenator(bundle, str(person_id_for(senator_id)), False, True)

    def _name_and_birth_matches(self, bundles) -> dict[str, list[str]]:
        if not bundles:
            return {}
        rows = self._run(
            "select_name_and_birth_matches", {"rows": [name_birth_row(b) for b in bundles]}
        )
        matches: dict[str, list[str]] = {}
        for row in rows:
            matches.setdefault(row["senator_id"], []).append(row["person_id"])
        return matches

    def _store_source_records(self, plan, accepted, source_id, outcome) -> dict:
        records = {}
        if plan.party_catalog_document:
            records.update(_keyed(document_record(plan.party_catalog_document)))
        for party in plan.parties:
            records.update(_keyed(party_record(party, plan.party_catalog_document)))
        for item in accepted:
            for document in bundle_documents(item.bundle):
                records.update(_keyed(document_record(document)))
            for affiliation in item.bundle.affiliations:
                records.update(_keyed(affiliation_record(affiliation)))
        rows = list(records.values())
        outcome.inserted["source_record"] += len(
            self._run("insert_source_records", {"source_id": source_id, "rows": rows})
        )
        keys = [
            {"external_key": r["external_key"], "content_sha256": r["content_sha256"]} for r in rows
        ]
        found = self._run("select_source_record_ids", {"source_id": source_id, "rows": keys})
        return {(row["external_key"], row["content_sha256"]): row["id"] for row in found}

    def _store_parties(self, plan, accepted, record_ids, outcome) -> None:
        used = {a.senate_party_code for item in accepted for a in item.bundle.affiliations}
        parties = [party for party in plan.parties if party.senate_party_code in used]
        counts = Counter(party.abbreviation.lower() for party in parties)
        taken = {
            row["abbreviation"]
            for row in self._run(
                "select_existing_abbreviations",
                {
                    "abbreviations": sorted(counts),
                    "own_codes": [party.code for party in parties],
                },
            )
        }
        rows = []
        for party in parties:
            record = party_record(party, plan.party_catalog_document)
            clash = party.abbreviation.lower() in taken or counts[party.abbreviation.lower()] > 1
            rows.append(
                {
                    "code": party.code,
                    "name": party.name,
                    "abbreviation": qualified_abbreviation(party) if clash else party.abbreviation,
                    "source_record_id": record_ids[
                        (record["external_key"], record["content_sha256"])
                    ],
                }
            )
        outcome.party_abbreviations = {row["code"]: row["abbreviation"] for row in rows}
        outcome.inserted["political_party"] += len(
            self._run("insert_political_parties", {"rows": rows})
        )

    def _store_people(self, accepted, source_id, record_ids, outcome) -> None:
        new_people, identifiers = [], []
        for item in accepted:
            identity = item.bundle.identity
            record_id = record_ids[_record_key(document_record(identity.document))]
            if item.has_identifier:
                continue
            if item.creates_person:
                new_people.append(
                    {
                        "person_id": item.person_id,
                        "civil_name": identity.civil_name,
                        "display_name": identity.display_name,
                        "birth_date": date_text(identity.birth_date),
                        "primary_record_id": record_id,
                        "normalized_name": name_birth_row(item.bundle)["normalized_name"],
                    }
                )
            identifiers.append(
                {
                    "senator_id": identity.senator_id,
                    "person_id": item.person_id,
                    "source_record_id": record_id,
                }
            )
        outcome.inserted["person"] += len(self._run("insert_people", {"rows": new_people}))
        outcome.inserted["person_identifier"] += len(
            self._run("insert_person_identifiers", {"source_id": source_id, "rows": identifiers})
        )

    def _store_terms_and_exercises(self, accepted, institution_id, record_ids, outcome) -> None:
        terms, exercises = [], []
        for item in accepted:
            mandates_id = _document_record_id(item.bundle.mandates_document, record_ids)
            for term in item.bundle.terms:
                terms.append(
                    {
                        "person_id": item.person_id,
                        "represented_uf": term.represented_uf,
                        "legislature_key": term.legislature_key,
                        "official_term_key": term_key(item.person_id, term.legislature_key),
                        "term_start": date_text(term.starts_on),
                        "term_end": date_text(term.ends_before),
                        "source_record_id": mandates_id,
                    }
                )
            for exercise in item.bundle.exercises:
                exercises.append(
                    {
                        "official_term_key": term_key(item.person_id, exercise.legislature_key),
                        "starts_on": date_text(exercise.starts_on),
                        "ends_before": date_text(exercise.ends_before),
                        "capacity": exercise.capacity,
                        "source_record_id": mandates_id,
                    }
                )
        parameters = {"institution_id": institution_id, "rows": terms}
        outcome.inserted["office_term"] += len(self._run("insert_office_terms", parameters))
        outcome.conflicts += _conflicts(
            "office_term", self._run("select_conflicting_terms", parameters)
        )
        parameters = {"institution_id": institution_id, "rows": exercises}
        outcome.inserted["office_exercise"] += len(self._run("insert_office_exercises", parameters))
        outcome.conflicts += _conflicts(
            "office_exercise", self._run("select_conflicting_exercises", parameters)
        )

    def _store_affiliations(self, accepted, record_ids, outcome) -> None:
        rows = []
        for item in accepted:
            for affiliation in item.bundle.affiliations:
                if affiliation.is_without_party:
                    continue
                record = affiliation_record(affiliation)
                rows.append(
                    {
                        "person_id": item.person_id,
                        "party_code": SENATE_PARTY_CODE_PREFIX + affiliation.senate_party_code,
                        "valid_from": date_text(affiliation.starts_on),
                        "valid_until": date_text(affiliation.ends_before),
                        "observed_on": date_text(affiliation.starts_on),
                        "source_record_id": record_ids[_record_key(record)],
                        "information_valid_from": affiliation.document.fetched_at.isoformat(),
                    }
                )
        parameters = {"scope": AFFILIATION_SCOPE, "rows": rows}
        outcome.inserted["political_party_affiliation"] += len(
            self._run("insert_affiliations", parameters)
        )
        outcome.conflicts += _conflicts(
            "political_party_affiliation",
            self._run("select_conflicting_affiliations", {"rows": rows}),
        )

    def _store_facts(self, accepted, record_ids, outcome) -> None:
        rows = []
        for item in accepted:
            rows.extend(_fact_rows(item, record_ids))
        outcome.inserted["person_fact"] += len(self._run("insert_person_facts", {"rows": rows}))


def _fact_rows(item: AcceptedSenator, record_ids) -> list[dict]:
    bundle, rows = item.bundle, []
    identity = bundle.identity
    rows.append(
        {
            "person_id": item.person_id,
            "field_name": f"{LOAD_NAME}:official_senator_identity",
            "value": {
                "senator_id": identity.senator_id,
                "civil_name": identity.civil_name,
                "display_name": identity.display_name,
                "birth_date": date_text(identity.birth_date),
                "source_url": identity.document.url,
                "source_sha256": identity.document.sha256,
            },
            "review_status": "verified",
            "source_record_id": _document_record_id(identity.document, record_ids),
        }
    )
    without_party = [a for a in bundle.affiliations if a.is_without_party]
    if without_party:
        rows.append(
            _interval_fact(item, "senate_no_affiliation_intervals", without_party, record_ids)
        )
    if bundle.year_only_claims:
        rows.append(_year_claim_fact(item, record_ids))
    return rows


def _interval_fact(item, field_name, affiliations, record_ids) -> dict:
    return {
        "person_id": item.person_id,
        "field_name": field_name,
        "value": [
            {
                "valid_from": date_text(a.starts_on),
                "valid_until": date_text(a.ends_before),
                "senate_record_key": affiliation_key(a),
            }
            for a in affiliations
        ],
        "review_status": "verified",
        "source_record_id": _document_record_id(item.bundle.affiliations_document, record_ids),
    }


def _year_claim_fact(item, record_ids) -> dict:
    return {
        "person_id": item.person_id,
        "field_name": "senate_affiliation_year_precision_claims",
        "value": [claim.raw_element for claim in item.bundle.year_only_claims],
        "review_status": "incomplete",
        "source_record_id": _document_record_id(item.bundle.affiliations_document, record_ids),
    }


def _keyed(record: dict) -> dict:
    return {_record_key(record): record}


def _record_key(record: dict) -> tuple[str, str]:
    return record["external_key"], record["content_sha256"]


def _document_record_id(document, record_ids) -> int:
    return record_ids[_record_key(document_record(document))]


def _review(code: str, senator_id: str, detail: str = "") -> PendingItem:
    return PendingItem(code, senator_id, detail, "all")


def _conflicts(table: str, rows: list) -> list[dict]:
    return [{"table": table, **dict(row)} for row in rows]
