"""Batch reads and evidence-backed source bridges for existing canonical people."""

from datetime import date

from psycopg.types.json import Jsonb

from normalization.identity import normalize_person_name
from service.identity_resolution.matching import PersonIdentityCandidate
from service.ingestion.contracts import IngestionError
from storage.files import hash_content


def fetch_electoral_identity_candidates(connection, uf, office_code, years) -> list:
    rows = connection.execute(
        "SELECT p.id,r.id AS source_record_id,r.payload FROM se_liga_brasil.person p "
        "JOIN se_liga_brasil.electoral_candidacy c ON c.person_id=p.id "
        "JOIN se_liga_brasil.source_record r ON r.id=c.source_record_id "
        "WHERE c.represented_uf=%s AND c.office_code=%s "
        "AND (%s::integer[] IS NULL OR c.election_year=ANY(%s))",
        (uf, office_code, list(years) if years else None, list(years) if years else None),
    ).fetchall()
    candidates = {}
    for row in rows:
        person_id, payload = str(row["id"]), row["payload"]
        candidate = candidates.setdefault(person_id, PersonIdentityCandidate(person_id))
        candidate.legal_names.add(normalize_person_name(payload["civilName"]))
        candidate.public_names.add(normalize_person_name(payload["displayName"]))
        if payload.get("birthDate"):
            candidate.birthdays.add(date.fromisoformat(payload["birthDate"]).strftime("%d/%m"))
        candidate.political_party_codes.add(payload.get("politicalPartyCode", ""))
        candidate.source_record_ids.add(row["source_record_id"])
    return list(candidates.values())


def fetch_payroll_recipients(connection, source_id) -> list:
    return connection.execute(
        "SELECT recipient_key,recipient_name,"
        "array_agg(DISTINCT source_record_id ORDER BY source_record_id) AS source_record_ids "
        "FROM se_liga_brasil.person_payroll_payment "
        "WHERE source_id=%s GROUP BY recipient_key,recipient_name",
        (source_id,),
    ).fetchall()


def build_identity_links(resolutions: list[dict], recipients: list[dict]) -> list:
    indexed = {row["recipient_key"]: row for row in recipients}
    links = []
    for resolution in resolutions:
        if (resolution["status"] != "matched"
                or resolution.get("method") == "exact_legal_name_and_electoral_scope"):
            continue
        recipient = indexed[resolution["recipient_key"]]
        evidence = resolution | {
            "published_name": recipient["recipient_name"],
            "payroll_source_record_ids": recipient["source_record_ids"],
            "derived_identity_resolution": True,
        }
        evidence = stable_identity_evidence(evidence)
        links.append(
            {
                "external_id": recipient["recipient_key"],
                "person_id": resolution["person_id"],
                "evidence": evidence,
                "hash": hash_content(evidence),
            }
        )
    return links


def apply_payroll_identity_links(connection, source_id, links: list, source_url: str) -> dict:
    """Evidence and identifier bridge commit together; no per-person remote queries."""
    if not links:
        return {"linked_payments": 0, "source_identities": 0}
    parameters = {"source_id": source_id, "links": Jsonb(links), "source_url": source_url}
    with connection.transaction():
        connection.execute("SET LOCAL statement_timeout='60s'")
        connection.execute(
            "SELECT pg_advisory_xact_lock(hashtext(%s))", (f"se_liga_brasil:identity:{source_id}",)
        )
        connection.execute(
            """
            CREATE TEMP TABLE identity_links ON COMMIT DROP AS
            SELECT value->>'external_id' AS external_id,(value->>'person_id')::uuid AS person_id,
                   value->'evidence' AS evidence,value->>'hash' AS hash
            FROM jsonb_array_elements(%(links)s::jsonb)
        """,
            parameters,
        )
        verify_identity_conflicts(connection, source_id)
        save_identity_evidence(connection, parameters)
        save_birth_date_reviews(connection, parameters)
        row = connection.execute(
            """
            WITH updated AS (
              UPDATE se_liga_brasil.person_payroll_payment p SET person_id=i.person_id,
                identity_status='verified',updated_at=now()
              FROM se_liga_brasil.person_identifier i
              WHERE i.source_id=%s AND i.namespace='payroll_recipient'
                AND p.source_id=i.source_id AND p.recipient_key=i.external_id
                AND p.person_id IS DISTINCT FROM i.person_id RETURNING p.id
            ) SELECT count(*) AS total FROM updated
        """,
            (source_id,),
        ).fetchone()
        connection.execute("DROP TABLE identity_links")
    return {"linked_payments": row["total"], "source_identities": len(links)}


def verify_identity_conflicts(connection, source_id) -> None:
    conflicts = connection.execute(
        """
        SELECT count(*) AS total FROM identity_links incoming
        JOIN se_liga_brasil.person_identifier current ON current.source_id=%s
         AND current.namespace='payroll_recipient' AND current.external_id=incoming.external_id
        WHERE current.person_id<>incoming.person_id
    """,
        (source_id,),
    ).fetchone()["total"]
    if conflicts:
        raise IngestionError("SOURCE_IDENTITY_BRIDGE_CONFLICT")


def save_identity_evidence(connection, parameters) -> None:
    connection.execute(
        """
        INSERT INTO se_liga_brasil.source_record(source_id,external_key,source_url,
          content_sha256,payload,effective_at)
        SELECT %(source_id)s,'identity:payroll_recipient:'||external_id,%(source_url)s,
          hash,evidence,now() FROM identity_links
        ON CONFLICT(source_id,external_key,content_sha256) DO NOTHING
    """,
        parameters,
    )
    connection.execute(
        """
        INSERT INTO se_liga_brasil.person_identifier(source_id,namespace,external_id,
          person_id,source_record_id)
        SELECT %(source_id)s,'payroll_recipient',i.external_id,i.person_id,r.id
        FROM identity_links i JOIN se_liga_brasil.source_record r
         ON r.source_id=%(source_id)s
         AND r.external_key='identity:payroll_recipient:'||i.external_id
         AND r.content_sha256=i.hash
        ON CONFLICT(source_id,namespace,external_id) DO UPDATE
          SET source_record_id=excluded.source_record_id
        WHERE se_liga_brasil.person_identifier.person_id=excluded.person_id
    """,
        parameters,
    )
    connection.execute(
        """
        INSERT INTO se_liga_brasil.person_fact(person_id,field_name,original_value,
          normalized_value,evidence_kind,review_status,source_record_id)
        SELECT i.person_id,'identity:payroll_recipient:'||i.external_id,i.evidence,i.evidence,
         'derived','verified',p.source_record_id FROM identity_links i
        JOIN se_liga_brasil.person_identifier p ON p.source_id=%(source_id)s
         AND p.namespace='payroll_recipient' AND p.external_id=i.external_id
        ON CONFLICT DO NOTHING
    """,
        parameters,
    )


def stable_identity_evidence(value):
    """Acquisition observations do not change an otherwise identical identity decision."""
    if isinstance(value, dict):
        return {
            key: stable_identity_evidence(item)
            for key, item in value.items()
            if key not in {"acquisition_status", "fetched_at"}
        }
    if isinstance(value, list):
        return [stable_identity_evidence(item) for item in value]
    return value


def fetch_reviewed_people(connection, cases, scope) -> dict:
    evidence = [
        {
            "legal_name": case["target_legal_name"],
            "normalized_name": normalize_person_name(case["target_legal_name"]),
            "birth_date": case["target_birth_date"],
        }
        for case in cases
    ]
    rows = connection.execute(
        """
        SELECT input.legal_name,p.id AS person_id,c.source_record_id,r.payload
        FROM jsonb_to_recordset(%s) input(legal_name text,normalized_name text,birth_date date)
        JOIN se_liga_brasil.person p ON p.normalized_name=input.normalized_name
          AND p.birth_date=input.birth_date
        JOIN se_liga_brasil.electoral_candidacy c ON c.person_id=p.id
        JOIN se_liga_brasil.source s ON s.id=c.source_id AND s.code='tse'
        JOIN se_liga_brasil.source_record r ON r.id=c.source_record_id
        WHERE c.election_year=%s AND c.represented_uf=%s AND c.office_code=%s
          AND NOT EXISTS(SELECT 1 FROM se_liga_brasil.person_identity_alias a
            WHERE a.alias_person_id=p.id)
        ORDER BY c.source_record_id
    """,
        (Jsonb(evidence), scope["election_year"], scope["uf"], scope["office_code"]),
    ).fetchall()
    people = {}
    for row in rows:
        existing = people.get(row["legal_name"])
        if existing and existing["person_id"] != row["person_id"]:
            raise IngestionError("REVIEWED_PERSONAL_IDENTITY_AMBIGUOUS")
        people[row["legal_name"]] = row
    return people


def save_birth_date_reviews(connection, parameters) -> None:
    connection.execute(
        """
        INSERT INTO se_liga_brasil.person_identity_review(source_record_id,
          suggested_person_id,reason_code)
        SELECT p.source_record_id,i.person_id,'CROSS_SOURCE_BIRTH_DAY_MONTH_DISAGREEMENT'
        FROM identity_links i JOIN se_liga_brasil.person_identifier p
          ON p.source_id=%(source_id)s AND p.namespace='payroll_recipient'
          AND p.external_id=i.external_id
        WHERE i.evidence->>'birth_conflict_preserved'='true'
        ON CONFLICT DO NOTHING
    """,
        parameters,
    )


def save_payroll_identity_reviews(connection, source_id, resolutions, recipients) -> int:
    """Keep insufficient personal evidence pending, without creating a person bridge."""
    pending = [row for row in resolutions if row["status"] == "requires_review"]
    if not pending:
        return 0
    indexed = {row["recipient_key"]: row for row in recipients}
    reviews = [
        {"source_record_id": record_id,
         "suggested_person_id": resolution["suggested_person_id"],
         "reason_code": resolution["reason_code"]}
        for resolution in pending
        for record_id in indexed[resolution["recipient_key"]]["source_record_ids"]
    ]
    row = connection.execute(
        """
        WITH inserted AS (
          INSERT INTO se_liga_brasil.person_identity_review(source_record_id,
            suggested_person_id,reason_code)
          SELECT input.source_record_id,input.suggested_person_id,input.reason_code
          FROM jsonb_to_recordset(%s) input(source_record_id bigint,
            suggested_person_id uuid,reason_code text)
          JOIN se_liga_brasil.source_record r ON r.id=input.source_record_id
            AND r.source_id=%s
          ON CONFLICT DO NOTHING RETURNING id
        ) SELECT count(*) AS total FROM inserted
        """, (Jsonb(reviews), source_id),
    ).fetchone()
    return row["total"]
