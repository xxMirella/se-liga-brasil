"""Explicit schema-local data reset with a private streaming CSV backup."""

from datetime import UTC, datetime
from pathlib import Path

from psycopg import sql

from service.ingestion.contracts import IngestionError
from storage.files import create_private_directory, save_json

SCHEMA_NAME = "se_liga_brasil"


class ProjectDataResetRepository:
    def __init__(self, connection, backup_root: Path, progress=None) -> None:
        self.connection = connection
        self.backup_root = backup_root
        self.progress = progress

    def reset_project_data(self) -> dict:
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        directory = self.backup_root / timestamp
        create_private_directory(directory)
        tables = self.connection.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname=%s ORDER BY tablename",
            (SCHEMA_NAME,),
        ).fetchall()
        if not tables:
            raise IngestionError("PROJECT_SCHEMA_NOT_FOUND")
        with self.connection.transaction():
            self.lock_ingestion()
            self.connection.execute("SET LOCAL lock_timeout='10s'")
            identifiers = [sql.Identifier(SCHEMA_NAME, row["tablename"]) for row in tables]
            table_list = sql.SQL(",").join(identifiers)
            self.connection.execute(
                sql.SQL("LOCK TABLE {} IN ACCESS EXCLUSIVE MODE").format(table_list)
            )
            backups = [self.backup_table(row["tablename"], directory) for row in tables]
            save_json(directory / "manifest.json", {"schema": SCHEMA_NAME, "tables": backups})
            self.connection.execute(
                sql.SQL("TRUNCATE TABLE {} RESTART IDENTITY").format(table_list)
            )
            self.connection.execute("REFRESH MATERIALIZED VIEW se_liga_brasil.person_profile")
        return {"backup_directory": str(directory), "cleared_tables": len(tables)}

    def lock_ingestion(self) -> None:
        acquired = self.connection.execute(
            "SELECT pg_try_advisory_xact_lock(hashtext(%s)) AS acquired",
            ("se_liga_brasil:ingestion:tse",),
        ).fetchone()["acquired"]
        if not acquired:
            raise IngestionError("CRAWLER_ALREADY_RUNNING_IN_DATABASE")
        running = self.connection.execute(
            "SELECT count(*) AS total FROM se_liga_brasil.ingestion_run WHERE status='running'"
        ).fetchone()["total"]
        if running:
            raise IngestionError("RUNNING_INGESTION_PREVENTS_RESET")

    def backup_table(self, table_name: str, directory: Path) -> dict:
        identifier = sql.Identifier(SCHEMA_NAME, table_name)
        path = directory / f"{table_name}.csv"
        rows = self.connection.execute(
            sql.SQL("SELECT count(*) AS total FROM {}").format(identifier)
        ).fetchone()["total"]
        with path.open("wb") as output, self.connection.cursor() as cursor:
            path.chmod(0o600)
            with cursor.copy(
                sql.SQL("COPY {} TO STDOUT WITH (FORMAT CSV,HEADER)").format(identifier)
            ) as copy:
                for block in copy:
                    output.write(bytes(block))
        if self.progress:
            self.progress("backup", table=table_name, rows=rows)
        return {"table": table_name, "rows": rows, "file": path.name, "bytes": path.stat().st_size}
