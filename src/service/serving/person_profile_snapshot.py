"""person_profile_snapshot: the raw reads of a rich person's profile, one row per person.

Scope (documented SQL, `SCOPE_SQL`): non-alias people with any mandate, proposition authorship,
payroll payment, or attendance / cabinet-payroll / ALERJ-activity fact. People known only by
electoral asset declarations stay out. The payload keeps what each of the profile reads returned
(see application.person_profile_reads); age, tenure, status and every other date-dependent
derivation still run in Python at read time. The build composes the profile with the very same
function the live path uses, so the recorded reads are exactly the ones the profile needs.
"""

import logging
from datetime import date
from hashlib import md5
from uuid import UUID

from service.serving.builder import DatasetSpec
from service.serving.person_profile_codec import decode_reads, encode_reads
from service.serving.release import SERVING_SCHEMA, current_release

logger = logging.getLogger(__name__)

DATASET_NAME = "person_profile_snapshot"
TABLE = f"{SERVING_SCHEMA}.{DATASET_NAME}"
COLUMNS_DDL = """person_id uuid PRIMARY KEY, payload jsonb NOT NULL,
  source_version text NOT NULL, as_of date NOT NULL"""
COLUMNS = ("person_id", "payload", "source_version", "as_of")
# Above this payload size the proposition page is left out of the row and read live (it is the
# only read with unbounded text: up to 100 items with up to 100 events each).
MAX_PAYLOAD_CHARS = 100_000

SCOPE_SQL = """SELECT p.id::text AS person_id FROM se_liga_brasil.person p
WHERE NOT EXISTS(SELECT 1 FROM se_liga_brasil.person_identity_alias a WHERE a.alias_person_id=p.id)
  AND (EXISTS(SELECT 1 FROM se_liga_brasil.office_term t WHERE t.person_id=p.id)
    OR EXISTS(SELECT 1 FROM se_liga_brasil.proposition_person l WHERE l.person_id=p.id)
    OR EXISTS(SELECT 1 FROM se_liga_brasil.person_payroll_payment y WHERE y.person_id=p.id)
    OR EXISTS(SELECT 1 FROM se_liga_brasil.person_fact f WHERE f.person_id=p.id
      AND (f.field_name LIKE 'camara\\_attendance:%'
        OR f.field_name LIKE 'senado\\_cabinet\\_payroll:%'
        OR f.field_name LIKE 'alerj\\_historical\\_activity:%')))
ORDER BY p.id"""


def collect_person_reads(connection, person_id: str, as_of: date) -> dict:
    """Compose the profile once with a recording source and return what it read."""
    from application.person_profile_loader import compose_profile
    from application.person_profile_reads import (
        PROPOSITIONS,
        LiveProfileSource,
        RecordingProfileSource,
    )

    source = RecordingProfileSource(LiveProfileSource(connection))
    compose_profile(source, person_id, as_of)
    if len(encode_reads(source.recorded)) > MAX_PAYLOAD_CHARS:
        source.recorded.pop(PROPOSITIONS, None)
    return source.recorded


def snapshot_rows(connection, person_ids, as_of: date, collect=collect_person_reads):
    """Lazy rows; a person whose reads fail is skipped (and served live) instead of the build."""
    for person_id in person_ids:
        try:
            with connection.transaction():  # savepoint: a failed read does not abort the build
                text = encode_reads(collect(connection, person_id, as_of))
        except Exception:
            logger.exception("person_profile_snapshot skipped %s", person_id)
            continue
        yield (person_id, text, md5(text.encode()).hexdigest(), as_of)


def person_profile_snapshot_spec(connection, as_of: date, *, today: date | None = None):
    """`today` is the portal's day (America/Belem), the date the reads are evaluated at."""
    today = today or _portal_today()
    person_ids = [row["person_id"] for row in connection.execute(SCOPE_SQL).fetchall()]
    return DatasetSpec(
        name=DATASET_NAME,
        columns_ddl=COLUMNS_DDL,
        columns=COLUMNS,
        rows=snapshot_rows(connection, person_ids, today),
    )


def _portal_today() -> date:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    return datetime.now(ZoneInfo("America/Belem")).date()


def read_stored_reads(connection, person_id, as_of: date) -> dict | None:
    """The recorded reads, or None (-> live path): no/old release, no row, other day, bad data."""
    try:
        person_id = str(UUID(person_id))
    except (ValueError, TypeError, AttributeError):
        return None  # the live path raises the proper validation error
    if current_release(connection, DATASET_NAME, as_of) is None:
        return None
    row = connection.execute(
        f"SELECT payload,as_of FROM {TABLE} WHERE person_id=%s::uuid", (person_id,)
    ).fetchone()
    if row is None or row["as_of"] != as_of:
        return None
    try:
        return decode_reads(row["payload"])
    except Exception:
        logger.exception("person_profile_snapshot undecodable for %s", person_id)
        return None
