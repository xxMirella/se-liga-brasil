"""Read consolidated attendance facts, never crawl during profile requests."""


def fetch_person_attendance(connection, person_id, as_of):
    row = connection.execute(
        """SELECT f.normalized_value AS attendance FROM se_liga_brasil.person_fact f
        WHERE f.person_id=%s AND f.field_name LIKE 'camara_attendance:%%'
          AND f.review_status='verified'
          AND f.normalized_value->>'period' < %s
          AND EXISTS (SELECT 1 FROM se_liga_brasil.office_exercise e
            JOIN se_liga_brasil.office_term t ON t.id=e.term_id
            JOIN se_liga_brasil.institution i ON i.id=t.institution_id
            WHERE t.person_id=f.person_id AND i.code='camara'
              AND e.starts_on<=%s AND (e.ends_before IS NULL OR e.ends_before>%s))
        ORDER BY f.normalized_value->>'period' DESC,
          f.normalized_value->>'sourceObservedAt' DESC,f.id DESC LIMIT 1""",
        (person_id, as_of.strftime("%Y-%m"), as_of, as_of),
    ).fetchone()
    return row["attendance"] if row else None


def fetch_person_attendance_history(connection, person_id, as_of):
    return [row["attendance"] for row in connection.execute(
        """SELECT DISTINCT ON (f.normalized_value->>'period')
          f.normalized_value AS attendance
        FROM se_liga_brasil.person_fact f
        WHERE f.person_id=%s AND f.field_name LIKE 'camara_attendance:%%'
          AND f.review_status='verified' AND f.normalized_value->>'period'>='2000-01'
          AND f.normalized_value->>'period'<=%s
        ORDER BY f.normalized_value->>'period',
          f.normalized_value->>'sourceObservedAt' DESC,f.id DESC""",
        (person_id, as_of.strftime("%Y-%m")),
    ).fetchall()]
