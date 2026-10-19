"""Read canonical votes in keyset batches; publication never reads original files."""

from datetime import date

from storage.files import write_json_line


def export_person_votes(connection, output_path, institution, year, *, maximum=100000):
    return export_vote_snapshot(
        connection, output_path, institution, year, fetch_vote_export_batch, maximum=maximum
    )


def export_person_voting_timeline(connection, output_path, institution, year, *, maximum=100000):
    return export_vote_snapshot(
        connection, output_path, institution, year, fetch_timeline_export_batch, maximum=maximum
    )


def export_vote_snapshot(connection, output_path, institution, year, fetch_batch, *, maximum):
    if not 1900 <= year <= 2200 or not 1 <= maximum <= 100000:
        raise ValueError("Invalid canonical export bounds")
    count, last_id, last_person = 0, 0, "00000000-0000-0000-0000-000000000000"
    with connection.transaction(), output_path.open("x", encoding="utf-8") as output:
        output_path.chmod(0o600)
        connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        while True:
            rows = fetch_batch(connection, institution, year, last_id, last_person)
            if not rows:
                return count
            for row in rows:
                if count >= maximum:
                    raise ValueError("Canonical export limit exceeded; no snapshot published")
                last_id, last_person = row["voting_id"], row["person_id"]
                row["voting_id"] = str(row["voting_id"])
                row["occurred_on"] = row["occurred_on"].isoformat()
                write_json_line(output, row)
                count += 1


def fetch_vote_export_batch(connection, institution, year, last_id, last_person):
    return fetch_vote_rows(connection, institution, year, last_id, last_person)


def fetch_timeline_export_batch(connection, institution, year, last_id, last_person):
    return fetch_vote_rows(connection, institution, year, last_id, last_person, include_matter=True)


def fetch_vote_rows(connection, institution, year, last_id, last_person, *, include_matter=False):
    matter_columns = """,
        nullif(p.kind,'unknown') AS matter_kind,p.number AS matter_number,p.year AS matter_year,
        nullif(p.title,'Objeto não informado') AS matter_name,
        nullif(trim(p.summary),'') AS description,
        CASE WHEN nullif(trim(p.summary),'') IS NULL THEN 'unknown'
          ELSE 'official_text' END AS description_origin,
        p.official_key AS official_url,v.subject AS voting_subject,v.round_number"""
    columns = matter_columns if include_matter else ""
    return connection.execute(
        f"""SELECT pv.person_id::text,v.id AS voting_id,i.code AS institution_code,
        coalesce(v.held_on,(v.held_at AT TIME ZONE 'America/Sao_Paulo')::date) AS occurred_on,
        'day' AS date_precision,pv.choice AS vote_choice,pv.participation_status,
        r.content_sha256 AS evidence_sha256,'verified' AS validation_status{columns}
        FROM se_liga_brasil.person_vote pv
        JOIN se_liga_brasil.voting v ON v.id=pv.voting_id
        JOIN se_liga_brasil.institution i ON i.id=v.institution_id
        JOIN se_liga_brasil.proposition p ON p.id=v.proposition_id
        JOIN se_liga_brasil.source_record r ON r.id=pv.source_record_id
        WHERE i.code=%s AND v.method='roll_call'
        AND pv.identity_method='unique_full_name_birth_date'
        AND coalesce(v.held_on,(v.held_at AT TIME ZONE 'America/Sao_Paulo')::date)>=%s
        AND coalesce(v.held_on,(v.held_at AT TIME ZONE 'America/Sao_Paulo')::date)<%s
        AND (v.id,pv.person_id)>(%s,%s::uuid)
        ORDER BY v.id,pv.person_id LIMIT 1000""",
        (institution, date(year, 1, 1), date(year + 1, 1, 1), last_id, last_person),
    ).fetchall()
