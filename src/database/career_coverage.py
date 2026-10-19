"""Bounded canonical fact reads; does not turn summary coverage into acquisition proof."""

MAX_CAREER_BATCH = 1000


def fetch_career_coverage_inputs(connection, person_ids):
    people = list(dict.fromkeys(person_ids))
    if len(people) > MAX_CAREER_BATCH:
        raise ValueError("Career coverage batch exceeds 1000 people")
    if not people:
        return {"candidacies": [], "exercises": [], "terms": []}
    candidacies = connection.execute(
        """SELECT person_id::text,election_year,represented_uf,election_result
        FROM se_liga_brasil.electoral_candidacy WHERE person_id=ANY(%s::uuid[])""",
        (people,),
    ).fetchall()
    terms = connection.execute(
        """SELECT t.person_id::text,t.id AS term_id,i.code AS institution,
          t.office_kind,t.term_start,t.term_end
        FROM se_liga_brasil.office_term t JOIN se_liga_brasil.institution i
          ON i.id=t.institution_id WHERE t.person_id=ANY(%s::uuid[])""",
        (people,),
    ).fetchall()
    exercises = connection.execute(
        """SELECT t.person_id::text,i.code AS institution,s.code AS source,
          e.starts_on,e.ends_before,t.office_kind
        FROM se_liga_brasil.office_exercise e
        JOIN se_liga_brasil.office_term t ON t.id=e.term_id
        JOIN se_liga_brasil.institution i ON i.id=t.institution_id
        JOIN se_liga_brasil.source_record r ON r.id=e.source_record_id
        JOIN se_liga_brasil.source s ON s.id=r.source_id
        WHERE t.person_id=ANY(%s::uuid[])""",
        (people,),
    ).fetchall()
    return {"candidacies": candidacies, "exercises": exercises, "terms": terms}


def coverage_receipts_available(connection):
    row = connection.execute(
        "SELECT to_regclass('se_liga_brasil.person_career_coverage_receipt') "
        "IS NOT NULL AS available"
    ).fetchone()
    return row["available"]


def fetch_coverage_receipts(connection, person_ids):
    from service.public_career_coverage.contracts import CoverageReceipt, CoverageScope

    people = list(dict.fromkeys(person_ids))
    if len(people) > MAX_CAREER_BATCH:
        raise ValueError("Career coverage batch exceeds 1000 people")
    if not people or not coverage_receipts_available(connection):
        return []
    rows = connection.execute(
        """SELECT *,person_id::text AS person_key
        FROM se_liga_brasil.person_career_coverage_receipt
        WHERE person_id=ANY(%s::uuid[])""",
        (people,),
    ).fetchall()
    return [
        CoverageReceipt(
            scope=CoverageScope(
                row["person_key"],
                row["institution"],
                row["domain"],
                row["starts_on"],
                row["ends_before"],
                row["source"],
                row["partition_key"],
            ),
            checked_on=row["checked_on"],
            identity_verified=row["identity_verified"],
            enumeration_complete=row["enumeration_complete"],
            source_period_complete=row["source_period_complete"],
            artifact_verified=row["artifact_verified"] and row["scope_verified"],
            status=row["acquisition_status"],
            artifact_sha256=row["artifact_sha256"],
            parser_version=row["parser_version"],
            scope_verified=row["scope_verified"],
        )
        for row in rows
    ]


def persist_coverage_receipts(connection, receipts):
    """Only bounded, traceable acquisitions enter storage; counts never establish EOF."""
    import re
    from dataclasses import asdict

    from psycopg.types.json import Jsonb

    records = []
    for receipt in receipts:
        if len(records) >= MAX_CAREER_BATCH:
            raise ValueError("Receipt batch exceeds 1000 records")
        if not re.fullmatch(r"[a-f0-9]{64}", receipt.artifact_sha256 or ""):
            raise ValueError("Receipt requires original artifact SHA256")
        if not receipt.parser_version or not receipt.parser_version.strip():
            raise ValueError("Receipt requires parser version")
        record = asdict(receipt)
        scope = record.pop("scope")
        scope.pop("applicability")
        record.update(scope)
        record["partition_key"] = record.pop("partition")
        record["acquisition_status"] = record.pop("status")
        records.append(record)
    if not records:
        return 0
    connection.execute(
        """INSERT INTO se_liga_brasil.person_career_coverage_receipt AS stored
        SELECT * FROM jsonb_populate_recordset(
          NULL::se_liga_brasil.person_career_coverage_receipt,%s)
        ON CONFLICT(person_id,institution,domain,source,partition_key,starts_on,ends_before)
        DO UPDATE SET checked_on=excluded.checked_on,
          identity_verified=excluded.identity_verified,
          enumeration_complete=excluded.enumeration_complete,
          source_period_complete=excluded.source_period_complete,
          artifact_verified=excluded.artifact_verified,scope_verified=excluded.scope_verified,
          artifact_sha256=excluded.artifact_sha256,parser_version=excluded.parser_version,
          acquisition_status=excluded.acquisition_status
        WHERE excluded.checked_on>=stored.checked_on""",
        (Jsonb(records, dumps=_dump_receipts),),
    )
    return len(records)


def _dump_receipts(records):
    import json

    return json.dumps(records, default=lambda value: value.isoformat())
