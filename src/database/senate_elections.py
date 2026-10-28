"""Lock only annual Senate partitions receiving election observations."""


def fetch_election_year_senate_partitions(connection, observations):
    years = sorted({row["election_year"] for row in observations})
    territories = sorted({row["territory_code"] for row in observations} | {"BR"})
    rows = connection.execute(
        "SELECT payload FROM se_liga_brasil.political_dashboard_annual "
        "WHERE institution_code='senado' AND year=ANY(%s) AND territory_code=ANY(%s) "
        "ORDER BY year,territory_code FOR UPDATE", (years, territories),
    ).fetchall()
    return [row["payload"] for row in rows]
