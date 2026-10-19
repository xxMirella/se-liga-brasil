"""Read-only, bounded asset projections using the existing person/year index."""

from database.public_profile import PublicProfileRepository


class PublicAssetsRepository(PublicProfileRepository):
    def fetch_asset_years(self, person_id, as_of):
        return self.connection.execute(
            """SELECT election_year,count(*) AS item_count,
              sum(declared_value) AS recorded_total,
              count(*) FILTER (WHERE value_quality_status<>'reported') AS review_count,
              max(source_generated_at) AS source_generated_at
            FROM se_liga_brasil.candidate_asset_declaration
            WHERE person_id=%s::uuid AND election_year<=%s
            GROUP BY election_year ORDER BY election_year DESC LIMIT 101""",
            (person_id, as_of.year),
        ).fetchall()

    def fetch_asset_items(self, person_id, years):
        return self.connection.execute(
            """SELECT election_year,asset_type,declared_value,value_quality_status,source_url
            FROM (
              SELECT a.election_year,a.asset_type,a.declared_value,a.value_quality_status,
                r.source_url,row_number() OVER (
                  PARTITION BY a.election_year ORDER BY a.id) AS position
              FROM se_liga_brasil.candidate_asset_declaration a
              JOIN se_liga_brasil.source_record r ON r.id=a.source_record_id
              WHERE a.person_id=%s::uuid AND a.election_year=ANY(%s::integer[])
            ) ranked WHERE position<=100 ORDER BY election_year DESC,position""",
            (person_id, years),
        ).fetchall()
