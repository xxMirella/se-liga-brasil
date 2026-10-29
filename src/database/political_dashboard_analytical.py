"""Indexed annual projections prevent scans of raw evidence on public requests."""

import json
from itertools import batched

from psycopg.types.json import Jsonb

from database.public_profile import PublicProfileRepository

PARTITION_UPSERT = """
INSERT INTO se_liga_brasil.political_dashboard_annual
 (year,territory_code,institution_code,content_sha256,payload)
SELECT year,territory_code,institution_code,content_sha256,payload
FROM jsonb_to_recordset(%s::jsonb) AS incoming(
 year integer,territory_code text,institution_code text,content_sha256 text,payload jsonb)
ON CONFLICT(year,territory_code,institution_code) DO UPDATE SET
 content_sha256=excluded.content_sha256,payload=excluded.payload,published_at=now()
WHERE political_dashboard_annual.content_sha256<>excluded.content_sha256
"""


HISTORY_COMPOSITION = """
jsonb_build_object(
 'institution_code',institution_code,'territory_code',territory_code,
 'office_kinds',payload->'office_kinds',
 'political_parties',payload->'political_parties','total',payload->'total',
 'coverage',payload->'coverage','snapshot_on',payload->'snapshot_on',
 'expected_seats',payload->'expected_seats',
 'documented_vacancies',payload->'documented_vacancies',
 'orientation_policy_version',payload->'orientation_policy_version',
 'aggregation_basis',payload->'aggregation_basis',
 'government_context_observations',(SELECT coalesce(jsonb_agg(jsonb_build_object(
   'date',context->'date','title',context->'title','organization',context->'organization',
   'relationship',context->'relationship','summary',context->'summary',
   'source_url',context->'source_url')),'[]'::jsonb)
   FROM jsonb_array_elements(CASE WHEN jsonb_typeof(
    payload->'government_context_observations')='array'
    THEN payload->'government_context_observations' ELSE '[]'::jsonb END) context),
 'institutional_status',payload->'institutional_status',
 'institutional_status_label',payload->'institutional_status_label',
 'current',CASE WHEN jsonb_typeof(payload->'current')='object' THEN
   jsonb_build_object('name',payload->'current'->'name',
    'person_id',payload->'current'->'person_id',
    'exercise_id',payload->'current'->'exercise_id',
    'source_url',payload->'current'->'official_url',
    'starts_on',payload->'current'->'starts_on','ends_before',payload->'current'->'ends_before',
    'observed_through',payload->'current'->'observed_through',
    'date_precision',payload->'current'->'date_precision',
    'exercise_capacity',payload->'current'->'exercise_capacity',
    'exercise_capacity_source_url',payload->'current'->'exercise_capacity_evidence'->0->'url',
    'political_party',payload->'current'->'political_party',
    'political_party_status',payload->'current'->'political_party_status',
    'political_party_periods',(SELECT coalesce(jsonb_agg(jsonb_build_object(
     'political_party',period->'political_party','starts_on',period->'starts_on',
     'ends_before',period->'ends_before',
     'source_url',period->'evidence'->0->'url','date_precision',period->'date_precision',
     'political_party_status',period->'political_party_status',
     'political_party_context',period->'political_party_context')),'[]'::jsonb)
     FROM jsonb_array_elements(CASE WHEN jsonb_typeof(
      payload->'current'->'political_party_periods')='array'
      THEN payload->'current'->'political_party_periods' ELSE '[]'::jsonb END) period)) END,
 'national_observations',(SELECT coalesce(jsonb_agg(jsonb_build_object(
   'name',event->'name','political_party',event->'political_party',
   'political_party_status',event->'political_party_status',
   'source_observed_on',event->'source_observed_on')),'[]'::jsonb)
   FROM jsonb_array_elements(coalesce(payload->'national_observations','[]'::jsonb)) event),
 'segments',(SELECT coalesce(jsonb_agg(jsonb_build_object(
   'name',segment->'name','person_id',segment->'person_id',
   'exercise_id',segment->'exercise_id','source_url',segment->'official_url',
   'starts_on',segment->'starts_on','ends_before',segment->'ends_before',
   'observed_through',segment->'observed_through',
   'date_precision',segment->'date_precision','exercise_capacity',segment->'exercise_capacity',
   'exercise_capacity_source_url',segment->'exercise_capacity_evidence'->0->'url',
   'political_party',segment->'political_party',
   'political_party_status',segment->'political_party_status',
   'political_party_periods',(SELECT coalesce(jsonb_agg(jsonb_build_object(
    'political_party',period->'political_party','starts_on',period->'starts_on',
    'ends_before',period->'ends_before',
     'source_url',period->'evidence'->0->'url','date_precision',period->'date_precision',
    'political_party_status',period->'political_party_status',
    'political_party_context',period->'political_party_context')),'[]'::jsonb)
    FROM jsonb_array_elements(CASE WHEN jsonb_typeof(
     segment->'political_party_periods')='array'
     THEN segment->'political_party_periods' ELSE '[]'::jsonb END) period))),'[]'::jsonb)
   FROM jsonb_array_elements(coalesce(payload->'segments','[]'::jsonb)) segment)
) AS composition
"""


HISTORY_ROW_LIMIT = 8192


class AnnualDashboardRepository(PublicProfileRepository):
    def __init__(self, connection, *, history_cache=None):
        super().__init__(connection)
        self.history_cache = history_cache

    def activate_partitions(self, partitions):
        from service.political_dashboard_dataset.storage import encode_partition

        with self.connection.transaction():
            for batch in batched(partitions, 128):
                rows = []
                for partition in batch:
                    _, digest = encode_partition(partition)
                    rows.append(
                        {
                            "year": partition["year"],
                            "territory_code": partition["territory_code"],
                            "institution_code": partition["institution_code"],
                            "content_sha256": digest,
                            "payload": partition,
                        }
                    )
                self.connection.execute(PARTITION_UPSERT, (Jsonb(rows),))
            self.refresh_history({partition["territory_code"] for partition in partitions})

    def fetch_current_official_assembly_rosters(self, year):
        return self.connection.execute(
            "SELECT payload FROM se_liga_brasil.political_dashboard_annual WHERE year=%s "
            "AND payload->>'aggregation_basis' IN ('verified_current_official_assembly_roster', "
            "'official_active_legislature_registry_not_individual_exercise_confirmation', "
            "'official_roster_reconciled_with_dated_exercise_evidence', "
            "'official_directory_during_reported_migration') "
            "ORDER BY territory_code,institution_code LIMIT 27",
            (year,),
        ).fetchall()

    def fetch_verified_camara_identities(self):
        rows = self.connection.execute(
            "SELECT i.external_id,i.person_id::text,i.source_record_id "
            "FROM se_liga_brasil.person_identifier i "
            "JOIN se_liga_brasil.source s ON s.id=i.source_id AND s.code='camara' "
            "JOIN se_liga_brasil.source_record r ON r.id=i.source_record_id "
            "WHERE i.namespace='federal_deputy' "
            "AND r.payload->>'identityMethod'='validated_cpf_or_unique_full_name_birth_date' "
            "AND NOT EXISTS(SELECT 1 FROM se_liga_brasil.person_identity_alias a "
            "WHERE a.alias_person_id=i.person_id)"
        ).fetchall()
        return {row["external_id"]: row for row in rows}

    def fetch_annual_snapshot(self, year, territories, history_end_year=None):
        """Selected-year partitions plus the territory histories.

        With the published history table this is one keyed statement and the histories come
        from the version-checked cache. Without it (before the migration, or a territory not
        yet published) the history is built from the annual rows, as before.
        """
        if self.history_cache is None:
            return self._fetch_annual_rows(year, territories, history_end_year)
        published = self._fetch_published_snapshot(year, territories)
        if published is not None:
            return published
        return self._fetch_unpublished_snapshot(year, territories, history_end_year)

    def _fetch_published_snapshot(self, year, territories):
        from database.political_dashboard_history import (
            PublishedHistoryReader,
            assemble_snapshot,
        )

        reader = PublishedHistoryReader(self.connection, self.history_cache)
        snapshot = reader.fetch_snapshot(year, territories)
        return assemble_snapshot(snapshot, self.history_cache) if snapshot else None

    def _fetch_unpublished_snapshot(self, year, territories, history_end_year=None):
        from service.political_dashboard_dataset.history import (
            expand_history_row,
            reduce_history_row,
        )

        snapshot = self._fetch_annual_rows(year, territories, history_end_year)
        snapshot["history"] = [
            expand_history_row(reduce_history_row(row)) for row in snapshot["history"]
        ]
        return snapshot

    def _fetch_annual_rows(self, year, territories, history_end_year=None):
        # A single SELECT has one PostgreSQL snapshot even in autocommit mode.
        return self.connection.execute(
            "WITH selected AS (SELECT payload FROM se_liga_brasil.political_dashboard_annual "
            "WHERE year=%s AND territory_code=ANY(%s) "
            "ORDER BY territory_code,institution_code LIMIT 32), "
            "history AS (SELECT year,institution_code,territory_code, "
            "payload->'office_kinds' AS office_kinds, "
            "coalesce((payload->>'source_observation_count')::integer, "
            "(payload->>'observed_people_count')::integer,(payload->>'total')::integer, "
            "jsonb_array_length(payload->'segments'),0) AS total, " + HISTORY_COMPOSITION + " "
            "FROM se_liga_brasil.political_dashboard_annual "
            "WHERE territory_code=ANY(%s) AND year BETWEEN 1826 AND %s "
            "ORDER BY year,territory_code,institution_code LIMIT 8192) "
            "SELECT coalesce((SELECT jsonb_agg(jsonb_build_object('payload',payload)) "
            "FROM selected),'[]'::jsonb) AS partitions, "
            "coalesce((SELECT jsonb_agg(to_jsonb(history)) FROM history),'[]'::jsonb) AS history",
            (year, territories, territories, history_end_year or year),
        ).fetchone()

    def existing_camara_historical_cohorts(self):
        return self.connection.execute(
            "SELECT DISTINCT payload->>'annual_cohort' AS annual_cohort "
            "FROM se_liga_brasil.political_dashboard_annual "
            "WHERE institution_code='camara' AND year BETWEEN 2000 AND 2025"
        ).fetchall()

    def build_history_entries(self, territories):
        """Publishable history of each territory, built from every annual row it has."""
        from service.political_dashboard_dataset.history import history_entry

        entries = []
        for territory in sorted(set(territories)):
            rows = self.fetch_history([territory], 9999)
            if len(rows) >= HISTORY_ROW_LIMIT:
                raise ValueError("HISTORY_SOURCE_ROW_LIMIT_REACHED")
            entries.append(history_entry(territory, rows))
        return entries

    def refresh_history(self, territories):
        """Keep published histories in step with the annual rows; no-op before the migration."""
        from database.political_dashboard_history import DashboardHistoryTable

        history = DashboardHistoryTable(self.connection)
        if not history.is_available():
            return 0
        return history.upsert(self.build_history_entries(territories))

    def remove_replaced_invalid_district_government(self):
        with self.connection.transaction():
            removed = self._delete_replaced_invalid_district_government()
            if removed:
                self.refresh_history({"DF"})
        return removed

    def _delete_replaced_invalid_district_government(self):
        return self.connection.execute(
            "DELETE FROM se_liga_brasil.political_dashboard_annual invalid "
            "WHERE invalid.year=2026 AND invalid.territory_code='DF' "
            "AND invalid.institution_code='state_government' AND EXISTS("
            "SELECT 1 FROM se_liga_brasil.political_dashboard_annual valid "
            "WHERE valid.year=invalid.year AND valid.territory_code='DF' "
            "AND valid.institution_code='district_government')"
        ).rowcount

    def fetch_government_partitions(self, year, territories):
        return self.connection.execute(
            "SELECT payload FROM se_liga_brasil.political_dashboard_annual "
            "WHERE year=%s AND territory_code=ANY(%s) "
            "AND institution_code IN ('state_government','district_government') "
            "ORDER BY territory_code,institution_code LIMIT 54",
            (year, territories),
        ).fetchall()

    def fetch_partitions(self, year, territories):
        with self.read_snapshot():
            return self.connection.execute(
                "SELECT payload FROM se_liga_brasil.political_dashboard_annual "
                "WHERE year=%s AND territory_code=ANY(%s) "
                "ORDER BY territory_code,institution_code LIMIT 32",
                (year, territories),
            ).fetchall()

    def fetch_history(self, territories, end_year):
        with self.read_snapshot():
            return self.connection.execute(
                "SELECT year,institution_code,territory_code,"
                "payload->'office_kinds' AS office_kinds,"
                "coalesce((payload->>'source_observation_count')::integer,"
                "(payload->>'observed_people_count')::integer,"
                "(payload->>'total')::integer,jsonb_array_length(payload->'segments'),0) AS total, "
                + HISTORY_COMPOSITION
                + " "
                "FROM se_liga_brasil.political_dashboard_annual "
                "WHERE territory_code=ANY(%s) AND year BETWEEN 1826 AND %s "
                "ORDER BY year,territory_code,institution_code LIMIT " + str(HISTORY_ROW_LIMIT),
                (territories, end_year),
            ).fetchall()

    def is_available(self):
        return self.connection.execute(
            "SELECT to_regclass('se_liga_brasil.political_dashboard_annual') IS NOT NULL AS exists"
        ).fetchone()["exists"]

    def activate_territorial_catalogs(self, catalogs):
        from service.political_dashboard_dataset.storage import encode_partition

        with self.connection.transaction():
            for catalog in catalogs:
                content, digest = encode_partition(catalog)
                self.connection.execute(
                    "INSERT INTO se_liga_brasil.political_dashboard_territory_catalog "
                    "(territory_code,content_sha256,payload) VALUES(%s,%s,%s::jsonb) "
                    "ON CONFLICT(territory_code) DO UPDATE SET "
                    "content_sha256=excluded.content_sha256,payload=excluded.payload,"
                    "published_at=now() "
                    "WHERE political_dashboard_territory_catalog.content_sha256"
                    "<>excluded.content_sha256",
                    (catalog["territory_code"], digest, content.decode()),
                )

    def fetch_territorial_catalog(self, uf):
        row = self.connection.execute(
            "SELECT payload FROM se_liga_brasil.political_dashboard_territory_catalog "
            "WHERE territory_code=%s",
            (uf,),
        ).fetchone()
        return row["payload"] if row else None

    def fetch_generation_hashes(self, year):
        return self.connection.execute(
            "SELECT territory_code,institution_code,content_sha256 "
            "FROM se_liga_brasil.political_dashboard_annual WHERE year=%s",
            (year,),
        ).fetchall()


def serialize_manifest(entries):
    return json.dumps(
        {"schema_version": "political_composition_annual_manifest.v1", "partitions": entries},
        sort_keys=True,
        separators=(",", ":"),
    )
