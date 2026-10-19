"""DuckDB bounded merge: partial files never delete other files' voting facts."""

from service.analytical_datasets.public_voting_timeline import PUBLIC_TIMELINE_COLUMNS
from service.analytical_datasets.storage import connect_analytical_engine

STATE_COLUMNS = PUBLIC_TIMELINE_COLUMNS | {
    "source_observed_at": "VARCHAR",
    "record_sha256": "VARCHAR",
    "evidence_sha256": "VARCHAR",
}


def write_merged_parquet(
    incoming_path,
    previous_state_path,
    public_path,
    state_path,
    spill_path,
    *,
    allow_reprojection=False,
):
    with connect_analytical_engine(spill_path) as connection:
        connection.read_json(
            str(incoming_path), columns=STATE_COLUMNS, format="newline_delimited"
        ).create("incoming")
        if previous_state_path is None:
            connection.sql("SELECT *,1 AS incoming_revision FROM incoming").create("combined")
        else:
            connection.read_parquet(str(previous_state_path), hive_partitioning=False).create(
                "previous"
            )
            connection.sql(
                "SELECT *,0 AS incoming_revision FROM previous UNION ALL BY NAME "
                "SELECT *,1 AS incoming_revision FROM incoming"
            ).create("combined")
        conflicts = connection.execute(
            """
            SELECT 1 FROM combined GROUP BY person_id,voting_id,source_observed_at
            HAVING count(DISTINCT record_sha256)>1 AND (
              NOT ? OR count(DISTINCT evidence_sha256)>1
              OR min(incoming_revision)=max(incoming_revision)) LIMIT 1
        """,
            [allow_reprojection],
        ).fetchone()
        if conflicts:
            raise ValueError("Conflicting facts share the same source observation timestamp")
        connection.sql("""
            SELECT * EXCLUDE(revision_rank,incoming_revision) FROM (
              SELECT *,row_number() OVER(PARTITION BY person_id,voting_id
                ORDER BY source_observed_at DESC,incoming_revision DESC,
                  record_sha256,evidence_sha256) AS revision_rank
              FROM combined)
            WHERE revision_rank=1 ORDER BY person_id,voting_id
        """).create("current_votes")
        connection.table("current_votes").write_parquet(str(state_path), compression="zstd")
        connection.execute("""
            CREATE TABLE public_votes AS SELECT current_votes.* FROM current_votes
            WHERE person_id!='__retired_voting__' AND NOT EXISTS (
              SELECT 1 FROM current_votes retired
              WHERE retired.person_id='__retired_voting__'
                AND retired.voting_id=current_votes.voting_id
                AND retired.source_observed_at>=current_votes.source_observed_at)
        """)
        columns = ",".join(PUBLIC_TIMELINE_COLUMNS)
        connection.sql(
            f"SELECT {columns} FROM public_votes ORDER BY person_id,voting_id"
        ).write_parquet(str(public_path), compression="zstd")
        return connection.execute("SELECT count(*) FROM public_votes").fetchone()[0]
