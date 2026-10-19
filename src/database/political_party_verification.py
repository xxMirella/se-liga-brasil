"""Batch persistence of official reports and auditable monthly-party verification."""

from collections import Counter

from psycopg.types.json import Jsonb

from service.political_party_verification.changes import verify_monthly_political_parties
from storage.files import hash_content


def persist_party_evidence(connection, source_id, source_url, records, field_name) -> None:
    if not records:
        return
    items = [row | {"hash": hash_content(row)} for row in records]
    parameters = {
        "items": Jsonb(items),
        "source_id": source_id,
        "source_url": source_url,
        "field_name": field_name,
    }
    connection.execute(
        """
        INSERT INTO se_liga_brasil.source_record(
          source_id,external_key,source_url,content_sha256,payload)
        SELECT %(source_id)s,%(field_name)s||':'||(item->>'hash'),
          coalesce(item->>'source_url',%(source_url)s),
          item->>'hash',item-'hash' FROM jsonb_array_elements(%(items)s) item
        ON CONFLICT DO NOTHING
    """,
        parameters,
    )
    connection.execute(
        """
        INSERT INTO se_liga_brasil.person_fact(person_id,field_name,original_value,
          normalized_value,evidence_kind,review_status,source_record_id)
        SELECT (item->>'person_id')::uuid,%(field_name)s,item-'hash',item-'hash','derived',
          CASE WHEN %(field_name)s='political_party_affiliation_report'
             OR item->>'status'='reported_change_confirmed' THEN 'verified' ELSE 'pending' END,r.id
        FROM jsonb_array_elements(%(items)s) item JOIN se_liga_brasil.source_record r
          ON r.source_id=%(source_id)s AND r.external_key=%(field_name)s||':'||(item->>'hash')
          AND r.content_sha256=item->>'hash' ON CONFLICT DO NOTHING
    """,
        parameters,
    )


def verify_payroll_political_parties(connection, source_id, source_url) -> dict:
    observations = connection.execute(
        """
        SELECT p.person_id::text,p.competence::text,p.source_record_id,
          r.payload->>'politicalPartyCode' AS political_party_code
        FROM se_liga_brasil.person_payroll_payment p
        JOIN se_liga_brasil.source_record r ON r.id=p.source_record_id
        WHERE p.source_id=%s AND p.person_id IS NOT NULL
          AND nullif(r.payload->>'politicalPartyCode','') IS NOT NULL
    """,
        (source_id,),
    ).fetchall()
    if not observations:
        return {"status": "source_does_not_report_political_party", "observations": 0}
    people = list({row["person_id"] for row in observations})
    rows = connection.execute(
        """
        SELECT normalized_value,source_record_id FROM se_liga_brasil.person_fact
        WHERE field_name='political_party_affiliation_report' AND person_id=ANY(%s::uuid[])
          AND review_status='verified'
    """,
        (people,),
    ).fetchall()
    reports = [
        row["normalized_value"] | {"source_record_id": row["source_record_id"]} for row in rows
    ]
    results = verify_monthly_political_parties(observations, reports)
    persist_party_evidence(
        connection, source_id, source_url, results, "political_party_change_verification"
    )
    return {
        "observations": len(results),
        "statuses": dict(Counter(row["status"] for row in results)),
    }
