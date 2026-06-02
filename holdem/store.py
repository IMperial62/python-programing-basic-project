from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .game import Table


class Store:
    def __init__(self, path: str = "data/holdem.sqlite") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("create table if not exists tables (id text primary key, snapshot text not null)")
            db.execute(
                "create table if not exists hand_history "
                "(id integer primary key autoincrement, table_id text, hand_no int, snapshot text not null, created_at datetime default current_timestamp)"
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def save(self, table: Table) -> None:
        snapshot = json.dumps(table.to_dict(), ensure_ascii=False)
        with self._connect() as db:
            db.execute("replace into tables(id, snapshot) values(?, ?)", (table.id, snapshot))
            if table.stage == "showdown":
                db.execute(
                    "insert into hand_history(table_id, hand_no, snapshot) values(?, ?, ?)",
                    (table.id, table.hand_no, snapshot),
                )

    def load(self, table_id: str) -> Table:
        with self._connect() as db:
            row = db.execute("select snapshot from tables where id = ?", (table_id,)).fetchone()
        if not row:
            raise KeyError(table_id)
        return Table.from_dict(json.loads(row[0]))

    def list_tables(self) -> list[dict]:
        with self._connect() as db:
            rows = db.execute("select id, snapshot from tables order by id").fetchall()
        return [{"id": row[0], "stage": json.loads(row[1]).get("stage")} for row in rows]
