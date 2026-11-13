"""In-memory stand-in for the serving schema: transactional DDL with snapshot rollback."""

import copy
import re
from contextlib import contextmanager
from datetime import UTC, datetime


class FakeServingConnection:
    def __init__(self):
        self.tables = {}
        self.releases = {}
        self.release_table_installed = True
        self.fail_on = None
        self.statements = []

    @contextmanager
    def transaction(self):
        snapshot = copy.deepcopy((self.tables, self.releases))
        try:
            yield
        except BaseException:
            self.tables, self.releases = snapshot
            raise

    @contextmanager
    def cursor(self):
        yield self

    def executemany(self, sql, batch):
        self.statements.append(sql)
        if self.fail_on and self.fail_on in sql:
            raise RuntimeError("simulated failure")
        self._table(re.search(r"INSERT INTO (\S+?)\(", sql).group(1))["rows"].extend(batch)

    def execute(self, sql, parameters=None):
        self.statements.append(sql)
        if self.fail_on and self.fail_on in sql:
            raise RuntimeError("simulated failure")
        self._result = None
        for pattern, handler in self._handlers():
            match = re.match(pattern, sql)
            if match:
                self._result = handler(match, parameters)
                break
        return self

    def fetchone(self):
        return self._result

    def _handlers(self):
        return [
            (r"CREATE TABLE (\S+) ", self._create),
            (r"DROP TABLE IF EXISTS (\S+)", self._drop),
            (r"ALTER TABLE (\S+) RENAME TO (\S+)", self._rename),
            (r"INSERT INTO (\S+?)\(.*VALUES\(%s,%s,clock", self._record),
            (r"INSERT INTO (\S+?)\(", self._insert_select),
            (r"SELECT count", self._measure),
            (r"SELECT name,version", self._select_release),
            (r"SELECT to_regclass", lambda m, p: {"installed": self.release_table_installed}),
        ]

    def _table(self, name):
        return self.tables[name]

    def _create(self, match, _):
        self.tables[match.group(1)] = {"rows": [], "indexes": []}

    def _drop(self, match, _):
        self.tables.pop(match.group(1), None)

    def _rename(self, match, _):
        source, target = match.group(1), "se_liga_brasil_serving." + match.group(2)
        self.tables[target] = self.tables.pop(source)

    def _insert_select(self, match, _):
        self._table(match.group(1))["rows"].append(("selected",))

    def _measure(self, *_):
        staging = next(name for name in self.tables if name.endswith("__staging"))
        rows = sorted(map(repr, self.tables[staging]["rows"]))
        return {"row_count": len(rows), "version": "|".join(rows)}

    def _record(self, _, parameters):
        name, version, as_of, row_count = parameters
        self.releases[name] = {
            "name": name,
            "version": version,
            "built_at": datetime.now(UTC),
            "as_of": as_of,
            "row_count": row_count,
        }

    def _select_release(self, _, parameters):
        return self.releases.get(parameters[0])
