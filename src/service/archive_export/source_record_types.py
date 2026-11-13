"""Single list of source_record types whose `payload` is archived and set to NULL (R4).

A type is the prefix of `source_record.external_key` before the first ':' (the entity kind the
reconciliation writes), scoped by `source.code`. Reviewed on 2026-11-12: no reader selects
`payload` of these types. Types deliberately NOT listed because something reads them:
  - tse `candidate` and `history`: `electoral_candidacy.source_record_id` points at them and
    person_identity.py, enrichment.py and tse/enrichment.py read `payload` through it;
  - Camara legislative kinds: public_propositions.py reads `payload->>'documentUrl'`;
  - payroll kinds: political_party_verification.py reads `politicalPartyCode`.
Adding a type here requires re-checking every reader (tests/test_source_record_payload_guard.py).
Keep db/migrations/0028_null_unread_source_record_payload.sql in sync (a test compares them).
"""

SOURCE_RECORD_TYPES_WITHOUT_PAYLOAD: dict[str, tuple[str, ...]] = {
    "alesp": ("alesp_attendance", "alesp_propositions"),
    "tse": ("asset", "complement"),
}


def source_record_payload_predicate_sql(record_alias: str, source_alias: str) -> str:
    """SQL boolean for rows of the listed types; aliases are code constants, not user input."""
    groups = []
    for source_code, types in sorted(SOURCE_RECORD_TYPES_WITHOUT_PAYLOAD.items()):
        quoted = ",".join(f"'{value}'" for value in types)
        groups.append(
            f"({source_alias}.code = '{source_code}' "
            f"AND split_part({record_alias}.external_key, ':', 1) IN ({quoted}))"
        )
    return "(" + " OR ".join(groups) + ")"
