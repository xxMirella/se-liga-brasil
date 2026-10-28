"""Only established verified institutional people may receive canonical roster links."""

from database.public_profile import PublicProfileRepository


class StateAssemblyRosterRepository(PublicProfileRepository):
    def ensure_official_source(self, source):
        self.connection.execute(
            "INSERT INTO se_liga_brasil.source(code,publisher,official_url,acquisition_method) "
            "VALUES(%s,%s,%s,%s) ON CONFLICT(code) DO NOTHING",
            (source.code, source.publisher, source.official_url, source.acquisition_method),
        )

    def fetch_verified_people(self, institution):
        rows = self.connection.execute(
            "SELECT DISTINCT ON (person_id) person_id::text,source_record_id::text "
            "FROM se_liga_brasil.person_fact f WHERE review_status='verified' "
            "AND field_name='current_public_office_observation' "
            "AND normalized_value->>'institutionCode'=%s "
            "AND NOT EXISTS(SELECT 1 FROM se_liga_brasil.person_identity_alias a "
            "WHERE a.alias_person_id=f.person_id) ORDER BY person_id,id DESC",
            (institution,),
        ).fetchall()
        return {row["person_id"]: row for row in rows}
