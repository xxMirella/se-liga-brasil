"""No new code may read source_record.payload without a review against the nulled types.

SOURCE_RECORD_TYPES_WITHOUT_PAYLOAD (service.archive_export.source_record_types) lists the types
whose payload migration 0028 sets to NULL. A file that reads `<alias>.payload` / `payload->` next
to `source_record` must be in KNOWN_PAYLOAD_READERS, with the reason it is safe for those types.
"""

import re
from pathlib import Path

from service.archive_export.source_record_types import (
    SOURCE_RECORD_TYPES_WITHOUT_PAYLOAD,
    source_record_payload_predicate_sql,
)

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD_READ = re.compile(r"\b[a-z_]+\.payload\b|\bpayload\s*->|\bpayload\s*#>")
EXCLUDED_PARTS = ("db/migrations/", "db/rollbacks/", "src/service/archive_export/")

KNOWN_PAYLOAD_READERS = {
    "src/database/public_propositions.py": "documentUrl of Camara proposition events only",
    "src/database/person_identity.py": "tse candidate/history via electoral_candidacy",
    "src/database/political_party_verification.py": "payroll kinds (politicalPartyCode)",
    "src/database/enrichment.py": "tse candidate/history via electoral_candidacy",
    "src/database/political_dashboard_analytical.py": "its own payload column, not source_record",
    "src/crawlers/tse/enrichment.py": "declaresAssets of the candidacy source record",
    "db/repairs/senate_podemos_affiliation_20261028.sql": "one-off senado repair",
    "db/ingestion/identities.sql": "previous tse candidate record (electionYear)",
    "db/ingestion/senado_historical_period.sql": "senado records copied on insert",
    "scripts/audit_name_only_payroll.py": "payroll audit (senado)",
}


def candidate_files():
    for folder in ("src", "db", "scripts"):
        for path in (ROOT / folder).rglob("*"):
            relative = path.relative_to(ROOT).as_posix()
            is_code = path.suffix in {".py", ".sql"} and relative != "db/schema.sql"
            if is_code and not relative.startswith(EXCLUDED_PARTS):
                yield relative, path


def test_only_reviewed_files_read_source_record_payload():
    readers = set()
    for relative, path in candidate_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "source_record" in text and PAYLOAD_READ.search(text):
            readers.add(relative)
    unreviewed = readers - set(KNOWN_PAYLOAD_READERS)
    assert not unreviewed, (
        f"{sorted(unreviewed)} read source_record.payload: confirm they never read the types in "
        "SOURCE_RECORD_TYPES_WITHOUT_PAYLOAD, then add them to KNOWN_PAYLOAD_READERS"
    )
    assert set(KNOWN_PAYLOAD_READERS) <= readers | {
        "db/repairs/senate_podemos_affiliation_20261028.sql"
    }


def test_reviewed_readers_do_not_name_the_nulled_types_next_to_payload():
    nulled = {value for types in SOURCE_RECORD_TYPES_WITHOUT_PAYLOAD.values() for value in types}
    for relative in KNOWN_PAYLOAD_READERS:
        text = (ROOT / relative).read_text(encoding="utf-8")
        for value in nulled - {"asset", "complement"}:
            assert value not in text, f"{relative} mentions nulled type {value}"


def test_migration_and_rollback_use_the_same_types_as_the_python_list():
    for name in (
        "db/migrations/0028_null_unread_source_record_payload.sql",
        "db/rollbacks/0028_restore_source_record_payload.sql",
    ):
        text = (ROOT / name).read_text(encoding="utf-8")
        for source_code, types in SOURCE_RECORD_TYPES_WITHOUT_PAYLOAD.items():
            quoted = ", ".join(f"'{value}'" for value in sorted(types))
            assert f"s.code = '{source_code}'" in text
            assert f"IN ({quoted})" in text


def test_predicate_mentions_every_listed_type():
    predicate = source_record_payload_predicate_sql("t", "s")
    for source_code, types in SOURCE_RECORD_TYPES_WITHOUT_PAYLOAD.items():
        assert f"s.code = '{source_code}'" in predicate
        assert all(f"'{value}'" in predicate for value in types)
