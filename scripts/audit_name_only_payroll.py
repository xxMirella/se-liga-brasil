"""Read-only repair preview; never changes identifiers, payments or source history."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from database.operations import connect_database  # noqa: E402

AUDIT_SQL = """
SELECT i.person_id,i.external_id,i.source_record_id,
 (SELECT count(*) FROM se_liga_brasil.person_payroll_payment pay
  WHERE pay.source_id=i.source_id AND pay.recipient_key=i.external_id
   AND pay.person_id=i.person_id) AS linked_payments,
 EXISTS(SELECT 1 FROM se_liga_brasil.person_document_identity d
  WHERE d.person_id=i.person_id) AS independent_document_available,
 (SELECT count(*) FROM se_liga_brasil.ingestion_entity e
  WHERE e.normalized_data->>'personId'=i.person_id::text
   AND e.entity_kind IN ('alesp_profile','camara_profile','senado_profile','alerj_profile')
   AND e.normalized_data->>'identityMethod' IN ('validated_cpf','unique_full_name_birth_date'))
   AS independently_verified_profiles,
 EXISTS(SELECT 1 FROM se_liga_brasil.source_record newer
  WHERE newer.source_id=i.source_id AND newer.external_key=r.external_key
   AND newer.payload->>'person_id'=i.person_id::text
   AND newer.payload->>'method' IN
    ('official_subject_bridge','reviewed_personal_identity_evidence')) AS stronger_payroll_evidence
FROM se_liga_brasil.person_identifier i
JOIN se_liga_brasil.source_record r ON r.id=i.source_record_id
JOIN se_liga_brasil.source s ON s.id=i.source_id
WHERE s.code='alesp' AND i.namespace='payroll_recipient'
 AND r.payload->>'method'='exact_legal_name_and_electoral_scope'
ORDER BY i.person_id
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    arguments = parser.parse_args()
    with connect_database(arguments.env_file) as connection:
        connection.execute("SET default_transaction_read_only=on")
        connection.execute("SET statement_timeout='30s'")
        rows = connection.execute(AUDIT_SQL).fetchall()
    print(json.dumps({"mode": "dry_run", "affected_identifiers": len(rows), "rows": rows,
                     "changes_applied": False}, default=str))


if __name__ == "__main__":
    main()
