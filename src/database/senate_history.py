"""Bounded existing projections and already verified source-person bridges."""


def fetch_existing_senate_partitions(connection, first_year, last_year):
    rows = connection.execute(
        "SELECT payload FROM se_liga_brasil.political_dashboard_annual "
        "WHERE institution_code='senado' AND year BETWEEN %s AND %s "
        "ORDER BY year,territory_code LIMIT 4096", (first_year, last_year),
    ).fetchall()
    return [row["payload"] for row in rows]


def fetch_verified_senator_identities(connection):
    rows = connection.execute(
        "SELECT i.external_id,i.person_id::text FROM se_liga_brasil.person_identifier i "
        "JOIN se_liga_brasil.source s ON s.id=i.source_id "
        "WHERE s.code='senado' AND i.namespace='senator' AND NOT EXISTS "
        "(SELECT 1 FROM se_liga_brasil.person_identity_alias a "
        "WHERE a.alias_person_id=i.person_id) LIMIT 4096"
    ).fetchall()
    return {row["external_id"]: row["person_id"] for row in rows}
