"""Private PostgreSQL access and explicit schema migration commands."""

import os
import re
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.rows import dict_row

from service.ingestion.contracts import IngestionError

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def connect_database(env_file: Path | None = None) -> psycopg.Connection:
    if env_file:
        load_dotenv(env_file, override=False)
    connection_string = os.getenv("DATABASE_URL") or os.getenv("SUPABASE_URL", "")
    if not re.match(r"^postgres(?:ql)?://", connection_string):
        raise IngestionError("POSTGRES_CONNECTION_REQUIRED")
    return psycopg.connect(
        session_connection_string(connection_string),
        prepare_threshold=None,
        autocommit=True,
        row_factory=dict_row,
        connect_timeout=15,
        application_name="se-liga-brasil-python",
    )


def session_connection_string(connection_string: str) -> str:
    """Crawler advisory locks need a persistent session, including through Supavisor."""
    parameters = conninfo_to_dict(connection_string)
    host = parameters.get("host", "")
    if host.endswith(".pooler.supabase.com") and parameters.get("port") == "6543":
        return make_conninfo(connection_string, port="5432")
    return connection_string


def read_sql_file(relative_path: str) -> str:
    return (PROJECT_ROOT / "db" / relative_path).read_text(encoding="utf-8")


def refresh_person_profiles(connection) -> None:
    with connection.transaction():
        connection.execute("SET LOCAL statement_timeout='120s'")
        connection.execute("SET LOCAL lock_timeout='10s'")
        connection.execute("REFRESH MATERIALIZED VIEW se_liga_brasil.person_profile")


def strip_transaction_wrapper(sql: str) -> str:
    return re.sub(r"COMMIT;\s*$", "", re.sub(r"^.*?\bBEGIN;", "", sql, count=1, flags=re.S))


def apply_ingestion_schema(connection) -> bool:
    with connection.transaction():
        connection.execute("SELECT pg_advisory_xact_lock(hashtext('se_liga_brasil:migrations'))")
        installed = connection.execute(
            "SELECT to_regclass('se_liga_brasil.ingestion_run') IS NOT NULL AS installed"
        ).fetchone()["installed"]
        applied = False
        if not installed:
            connection.execute(
                strip_transaction_wrapper(read_sql_file("migrations/0003_tse_ingestion.sql"))
            )
            applied = True
        identity_installed = connection.execute(
            "SELECT to_regclass('se_liga_brasil.person_document_identity') IS NOT NULL AS installed"
        ).fetchone()["installed"]
        if not identity_installed:
            connection.execute(
                strip_transaction_wrapper(
                    read_sql_file("migrations/0004_identity_and_affiliation.sql")
                )
            )
            applied = True
        observation_installed = connection.execute(
            "SELECT to_regclass('se_liga_brasil.political_party_observation') "
            "IS NOT NULL AS installed"
        ).fetchone()["installed"]
        if observation_installed:
            connection.execute(
                strip_transaction_wrapper(
                    read_sql_file("migrations/0005_remove_political_party_observation.sql")
                )
            )
            applied = True
        extensions_applied = apply_ingestion_extensions(connection)
        return applied or extensions_applied


def apply_ingestion_extensions(connection):
    appliers = (
        apply_payroll_schema,
        apply_internal_identity_schema,
        apply_parliamentary_enrichment_schema,
        apply_data_gap_schema,
        apply_source_policy_schema,
        apply_gap_cleanup_schema,
        apply_person_public_office_schema,
        apply_collection_routes_schema,
        apply_optional_proposition_number_schema,
        apply_business_relationship_schema,
        apply_legislative_voting_schema,
        apply_career_receipt_schema,
        apply_voting_refresh_queue_schema,
        apply_office_legal_scope_schema,
    )
    # Materialize results before any(): every migration must run even after a change.
    results = [applier(connection) for applier in appliers]
    return any(results)


def verify_schema(connection) -> dict:
    result = connection.execute("""
        SELECT count(*)::int AS tables,count(*) FILTER(WHERE rowsecurity)::int AS rls_tables
        FROM pg_tables WHERE schemaname='se_liga_brasil'
    """).fetchone()
    permissions = connection.execute("""
        SELECT count(*)::int AS exposed_roles FROM pg_roles 
        WHERE rolname IN ('anon','authenticated')
        AND has_schema_privilege(oid,'se_liga_brasil','USAGE')
    """).fetchone()
    if (
        result["tables"] not in {23, 32, 36, 37, 38, 39, 42, 43, 44, 45, 46}
        or result["tables"] != result["rls_tables"]
    ):
        raise IngestionError("SCHEMA_VERIFICATION_FAILED")
    if permissions["exposed_roles"]:
        raise IngestionError("SCHEMA_UNEXPECTEDLY_PUBLIC")
    return result | permissions


def apply_payroll_schema(connection) -> bool:
    applied = False
    payroll_installed = connection.execute(
        "SELECT to_regclass('se_liga_brasil.person_payroll_payment') IS NOT NULL AS installed"
    ).fetchone()["installed"]
    if not payroll_installed:
        connection.execute(
            strip_transaction_wrapper(read_sql_file("migrations/0006_payroll_payments.sql"))
        )
        applied = True
    quality_installed = connection.execute(
        "SELECT EXISTS(SELECT 1 FROM information_schema.columns "
        "WHERE table_schema='se_liga_brasil' "
        "AND table_name='candidate_asset_declaration' "
        "AND column_name='value_quality_status') AS installed"
    ).fetchone()["installed"]
    if not quality_installed:
        connection.execute(
            strip_transaction_wrapper(read_sql_file("migrations/0007_signed_asset_values.sql"))
        )
        applied = True
    return applied


def apply_internal_identity_schema(connection) -> bool:
    installed = connection.execute(
        "SELECT EXISTS(SELECT 1 FROM pg_constraint "
        "WHERE conrelid='se_liga_brasil.person_identifier'::regclass "
        "AND conname='person_identifier_no_electoral_identity') AS installed"
    ).fetchone()["installed"]
    if installed:
        return False
    connection.execute(
        strip_transaction_wrapper(read_sql_file("migrations/0008_internal_person_identity.sql"))
    )
    return True


def apply_parliamentary_enrichment_schema(connection) -> bool:
    nullable = connection.execute(
        "SELECT is_nullable='YES' AS nullable FROM information_schema.columns "
        "WHERE table_schema='se_liga_brasil' AND table_name='proposition' AND column_name='year'"
    ).fetchone()["nullable"]
    if nullable:
        return False
    connection.execute(
        strip_transaction_wrapper(read_sql_file("migrations/0009_optional_proposition_year.sql"))
    )
    return True


def apply_data_gap_schema(connection) -> bool:
    installed = connection.execute(
        "SELECT to_regclass('se_liga_brasil.person_data_gap') IS NOT NULL AS installed"
    ).fetchone()["installed"]
    if installed:
        return False
    connection.execute(
        strip_transaction_wrapper(read_sql_file("migrations/0010_person_data_gap.sql"))
    )
    return True


def apply_source_policy_schema(connection) -> bool:
    installed = connection.execute(
        "SELECT to_regclass('se_liga_brasil.source_request_policy') IS NOT NULL AS installed"
    ).fetchone()["installed"]
    if installed:
        return False
    connection.execute(
        strip_transaction_wrapper(read_sql_file("migrations/0011_source_request_policy.sql"))
    )
    return True


def apply_gap_cleanup_schema(connection) -> bool:
    installed = connection.execute(
        "SELECT EXISTS(SELECT 1 FROM information_schema.columns "
        "WHERE table_schema='se_liga_brasil' "
        "AND table_name='person_data_gap' AND column_name='is_processed') AS installed"
    ).fetchone()["installed"]
    if installed:
        return False
    connection.execute(
        strip_transaction_wrapper(read_sql_file("migrations/0012_processed_gap_cleanup.sql"))
    )
    return True


def apply_person_public_office_schema(connection) -> bool:
    installed = connection.execute(
        "SELECT EXISTS(SELECT 1 FROM information_schema.columns "
        "WHERE table_schema='se_liga_brasil' AND table_name='person' "
        "AND column_name='has_current_public_office') AS installed"
    ).fetchone()["installed"]
    if installed:
        return False
    connection.execute(
        strip_transaction_wrapper(read_sql_file("migrations/0013_person_current_public_office.sql"))
    )
    return True


def apply_collection_routes_schema(connection) -> bool:
    installed = connection.execute(
        "SELECT EXISTS(SELECT 1 FROM pg_constraint WHERE connamespace="
        "'se_liga_brasil'::regnamespace AND conname='person_data_gap_assigned_source_check' "
        "AND pg_get_constraintdef(oid) LIKE '%%alerj%%') AS installed"
    ).fetchone()["installed"]
    if installed:
        return False
    connection.execute(
        strip_transaction_wrapper(read_sql_file("migrations/0014_collection_source_routes.sql"))
    )
    return True


def apply_optional_proposition_number_schema(connection) -> bool:
    installed = connection.execute(
        "SELECT is_nullable='YES' AS installed FROM information_schema.columns "
        "WHERE table_schema='se_liga_brasil' AND table_name='proposition' AND column_name='number'"
    ).fetchone()["installed"]
    if installed:
        return False
    connection.execute(
        strip_transaction_wrapper(read_sql_file("migrations/0015_optional_proposition_number.sql"))
    )
    return True


def apply_business_relationship_schema(connection) -> bool:
    installed = connection.execute(
        "SELECT count(*)=3 AS installed FROM information_schema.tables "
        "WHERE table_schema='se_liga_brasil' AND table_name IN "
        "('business','business_establishment','person_business_relationship_observation')"
    ).fetchone()["installed"]
    if installed:
        return False
    connection.execute(
        strip_transaction_wrapper(read_sql_file("migrations/0016_business_relationships.sql"))
    )
    return True


def apply_legislative_voting_schema(connection):
    return apply_extension_table(connection, "person_vote_revision", "0017_legislative_voting.sql")


def apply_career_receipt_schema(connection):
    return apply_extension_table(
        connection, "person_career_coverage_receipt", "0018_career_coverage_receipts.sql"
    )


def apply_extension_table(connection, table_name, filename):
    installed = connection.execute(
        "SELECT to_regclass(%s) IS NOT NULL AS installed",
        ("se_liga_brasil." + table_name,),
    ).fetchone()["installed"]
    if installed:
        return False
    connection.execute(strip_transaction_wrapper(read_sql_file("migrations/" + filename)))
    return True


def apply_voting_refresh_queue_schema(connection):
    return apply_extension_table(connection, "voting_refresh_job", "0019_voting_refresh_queue.sql")


def apply_office_legal_scope_schema(connection):
    return apply_extension_table(
        connection, "office_legal_scope_version", "0020_office_legal_scope_versions.sql"
    )
