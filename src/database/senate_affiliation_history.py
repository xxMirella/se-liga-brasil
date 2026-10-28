"""Persist official historical affiliations through an existing verified Senate identity."""

import hashlib
import json
from datetime import UTC, datetime

from psycopg.types.json import Jsonb

SCOPE = "institution:senado:historical_affiliations"


def persist_senate_affiliation_history(connection, senator_code, raw_bytes, intervals, archive):
    """One transaction; preserve current observations, source IDs and historical unknowns."""
    with connection.transaction():
        connection.execute("SET LOCAL lock_timeout='10s'")
        identity = _verified_identity(connection, senator_code)
        political_parties = _unique_political_parties(connection, intervals)
        source_record_id = _save_source(connection, identity, senator_code, raw_bytes, archive)
        saved = _save_affiliations(
            connection, identity["person_id"], source_record_id, political_parties, intervals,
        )
        no_affiliation = [row for row in intervals if row["political_party"] == "S/Partido"]
        if no_affiliation:
            _save_no_affiliation(
                connection, identity["person_id"], source_record_id, no_affiliation,
            )
    return {"person_id": identity["person_id"], "source_record_id": source_record_id,
            "affiliation_ids": saved, "no_affiliation_intervals": len(no_affiliation)}


def _verified_identity(connection, senator_code):
    rows = connection.execute(
        "SELECT i.person_id::text,i.source_id FROM se_liga_brasil.person_identifier i "
        "JOIN se_liga_brasil.source s ON s.id=i.source_id "
        "WHERE s.code='senado' AND i.namespace='senator' AND i.external_id=%s "
        "AND NOT EXISTS (SELECT 1 FROM se_liga_brasil.person_identity_alias a "
        "WHERE a.alias_person_id=i.person_id)", (str(senator_code),),
    ).fetchall()
    if len(rows) != 1:
        raise ValueError("UNIQUE_VERIFIED_SENATOR_IDENTITY_REQUIRED")
    return rows[0]


def _unique_political_parties(connection, intervals):
    abbreviations = sorted({row["political_party"] for row in intervals} - {"S/Partido"})
    affiliated = [row for row in intervals if row["political_party"] != "S/Partido"]
    if len(affiliated) != len(abbreviations):
        raise ValueError("REPEATED_POLITICAL_PARTY_REQUIRES_PER_INTERVAL_SOURCE_RECORDS")
    rows = connection.execute(
        "SELECT abbreviation,min(id) id,count(*) count FROM se_liga_brasil.political_party "
        "WHERE abbreviation=ANY(%s) GROUP BY abbreviation", (abbreviations,),
    ).fetchall()
    if {row["abbreviation"] for row in rows} != set(abbreviations) or any(
            row["count"] != 1 for row in rows):
        raise ValueError("UNIQUE_EXISTING_POLITICAL_PARTY_REQUIRED")
    return {row["abbreviation"]: row["id"] for row in rows}


def _save_source(connection, identity, senator_code, raw_bytes, archive):
    digest = hashlib.sha256(raw_bytes).hexdigest()
    url = f"https://legis.senado.leg.br/dadosabertos/senador/{senator_code}/filiacoes.json"
    return connection.execute(
        "INSERT INTO se_liga_brasil.source_record(source_id,external_key,source_url,"
        "content_sha256,fetched_at,payload,storage_reference) VALUES(%s,%s,%s,%s,%s,%s,%s) "
        "ON CONFLICT(source_id,external_key,content_sha256) DO UPDATE "
        "SET source_url=excluded.source_url RETURNING id",
        (identity["source_id"], f"senator:{senator_code}:historical_affiliations", url, digest,
         datetime.now(UTC), Jsonb(json.loads(raw_bytes)), str(archive)),
    ).fetchone()["id"]


def _save_affiliations(connection, person_id, source_record_id, political_parties, intervals):
    rows = [dict(row, political_party_id=political_parties[row["political_party"]])
            for row in intervals if row["political_party"] != "S/Partido"]
    result = connection.execute(
        "INSERT INTO se_liga_brasil.political_party_affiliation(person_id,political_party_id,"
        "valid_from,valid_until,observed_on,source_record_id,information_valid_from,"
        "information_scope,evidence_kind) "
        "SELECT %s,r.political_party_id,r.valid_from,r.valid_until,%s,%s,%s,%s,'administrative' "
        "FROM jsonb_to_recordset(%s) r(political_party_id bigint,valid_from date,valid_until date) "
        "ON CONFLICT(person_id,political_party_id,source_record_id) DO UPDATE "
        "SET valid_from=excluded.valid_from,valid_until=excluded.valid_until RETURNING id",
        (person_id, datetime.now(UTC).date(), source_record_id, datetime.now(UTC), SCOPE,
         Jsonb(rows)),
    ).fetchall()
    return [row["id"] for row in result]


def _save_no_affiliation(connection, person_id, source_record_id, intervals):
    connection.execute(
        "INSERT INTO se_liga_brasil.person_fact(person_id,field_name,original_value,"
        "normalized_value,evidence_kind,review_status,source_record_id) "
        "VALUES(%s,'senate_no_affiliation_intervals',%s,%s,'administrative','verified',%s) "
        "ON CONFLICT(person_id,field_name,source_record_id) DO NOTHING",
        (person_id, Jsonb(intervals), Jsonb(intervals), source_record_id),
    )
