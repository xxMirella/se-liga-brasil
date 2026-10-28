"""Read existing publication scopes in one batch before adding historical galleries."""


def existing_gallery_partitions(connection, territories, first_year, last_year):
    rows = connection.execute(
        "SELECT year,territory_code,institution_code,payload "
        "FROM se_liga_brasil.political_dashboard_annual "
        "WHERE territory_code=ANY(%s) AND year BETWEEN %s AND %s "
        "AND institution_code IN ('state_government','municipal_government')",
        (list(territories), first_year, last_year),
    ).fetchall()
    return {(row['year'], row['territory_code'], row['institution_code']): row['payload']
            for row in rows}
