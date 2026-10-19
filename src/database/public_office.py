"""Refresh the person snapshot from verified public-office evidence in one batch."""

from database.operations import read_sql_file


def refresh_current_public_offices(connection) -> None:
    connection.execute(
        read_sql_file("ingestion/person_current_public_office.sql"), {"records": None}
    )
