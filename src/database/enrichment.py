"""Set-based missing-data planning and personal-evidence matching."""

from normalization.identity import normalize_person_name
from service.identity_resolution.evidence import IdentityEvidenceBuilder, load_identity_key
from service.ingestion.contracts import IngestionError


def fetch_enrichment_candidates(connection, person_id=None, ufs=None) -> list:
    return connection.execute(
        """
        SELECT p.id::text AS person_id,p.civil_name,p.display_name,p.birth_date,
          array_agg(DISTINCT r.payload->>'civilName') AS civil_names,
          array_agg(DISTINCT r.payload->>'displayName') AS public_names,
          coalesce(bool_or(c.office_code='6'),false)
            OR coalesce(p.current_public_office_kind='federal_deputy',false)
              AS has_federal_candidacy,
          coalesce(bool_or(c.office_code='7'),false)
            OR coalesce(p.current_public_office_kind='state_deputy',false) AS has_state_candidacy,
          EXISTS(SELECT 1 FROM se_liga_brasil.candidate_asset_declaration a
            WHERE a.person_id=p.id) AS has_declared_assets,
          EXISTS(SELECT 1 FROM se_liga_brasil.person_payroll_payment pay
            WHERE pay.person_id=p.id AND pay.organization_code='camara') AS has_payroll,
          EXISTS(SELECT 1 FROM se_liga_brasil.person_data_coverage coverage
            JOIN se_liga_brasil.source s ON s.id=coverage.source_id AND s.code='camara'
            WHERE coverage.person_id=p.id AND coverage.area='profile'
              AND coverage.checked_at>now()-interval '24 hours') AS recently_checked
        FROM se_liga_brasil.person p
        LEFT JOIN se_liga_brasil.electoral_candidacy c ON c.person_id=p.id
        LEFT JOIN se_liga_brasil.source_record r ON r.id=c.source_record_id
        WHERE (%s::uuid IS NULL OR p.id=%s::uuid)
          AND (%s::text[] IS NULL OR c.represented_uf=ANY(%s) OR c.person_id IS NULL)
          AND NOT EXISTS(SELECT 1 FROM se_liga_brasil.person_identity_alias a
            WHERE a.alias_person_id=p.id)
        GROUP BY p.id ORDER BY p.id
    """,
        (person_id, person_id, list(ufs) if ufs else None, list(ufs) if ufs else None),
    ).fetchall()


def match_official_person(connection, profile, expected_person_id) -> str:
    evidence = IdentityEvidenceBuilder(load_identity_key()).build_evidence(
        profile["nomeCivil"], cpf=profile.get("cpf")
    )
    if evidence["documentFingerprint"]:
        rows = connection.execute(
            """
            SELECT person_id::text FROM se_liga_brasil.person_document_identity
            WHERE document_kind='cpf' AND document_fingerprint=%s
        """,
            (evidence["documentFingerprint"],),
        ).fetchall()
        method = "validated_cpf"
    else:
        rows = connection.execute(
            """
            SELECT id::text AS person_id FROM se_liga_brasil.person
            WHERE normalized_name=%s AND birth_date=%s::date
              AND NOT EXISTS(SELECT 1 FROM se_liga_brasil.person_identity_alias a
                WHERE a.alias_person_id=id)
        """,
            (normalize_person_name(profile["nomeCivil"]), profile.get("dataNascimento")),
        ).fetchall()
        method = "unique_full_name_birth_date"
    if len(rows) != 1 or rows[0]["person_id"] != expected_person_id:
        raise IngestionError("OFFICIAL_PERSONAL_IDENTITY_NOT_CONFIRMED")
    return method
