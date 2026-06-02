from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .game import Table
from .store import Store

ROOT = Path(__file__).resolve().parent.parent
WEB_ROOT = ROOT / "web"
ASSET_ROOT = ROOT / "assets"
STORE = Store()

CONTENT_TYPES = {
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".html": "text/html; charset=utf-8",
}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            return self._file(WEB_ROOT / "index.html")
        if path in ("/styles.css", "/app.js"):
            return self._file(WEB_ROOT / path.lstrip("/"))
        if path.startswith("/assets/"):
            return self._asset(path.removeprefix("/assets/"))
        if path == "/api/health":
            return self._json({"ok": True})
        if path == "/api/tables":
            return self._json({"tables": STORE.list_tables()})
        if path.startswith("/api/tables/"):
            return self._with_table(path.split("/")[-1], lambda table: self._json(table.visible_state()))
        self._json({"error": "not found"}, 404)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        body = self._body()
        if path == "/api/tables":
            table = Table.create(seats=int(body.get("players", 3)), chips=int(body.get("chips", 1000)))
            STORE.save(table)
            return self._json(table.visible_state(), 201)
        if path.endswith("/action"):
            table_id = path.split("/")[-2]
            return self._with_table(table_id, lambda table: self._action(table, body))
        if path.endswith("/bot-action"):
            table_id = path.split("/")[-2]
            return self._with_table(table_id, self._bot_action)
        if path.endswith("/new-hand"):
            table_id = path.split("/")[-2]
            return self._with_table(table_id, self._new_hand)
        self._json({"error": "not found"}, 404)

    def _action(self, table: Table, body: dict) -> None:
        table.apply_action(body.get("player_id", "p1"), body.get("action", "check"), int(body.get("amount", 0)))
        STORE.save(table)
        self._json(table.visible_state())

    def _bot_action(self, table: Table) -> None:
        table.play_bot_turn()
        STORE.save(table)
        self._json(table.visible_state())

    def _new_hand(self, table: Table) -> None:
        table.start_hand()
        STORE.save(table)
        self._json(table.visible_state())

    def _with_table(self, table_id: str, callback) -> None:
        try:
            callback(STORE.load(table_id))
        except KeyError:
            self._json({"error": "table not found"}, 404)
        except ValueError as exc:
            self._json({"error": str(exc)}, 400)

    def _body(self) -> dict:
        size = int(self.headers.get("content-length", 0))
        if not size:
            return {}
        return json.loads(self.rfile.read(size).decode("utf-8"))

    def _json(self, data: dict, status: int = 200) -> None:
        encoded = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("content-length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _asset(self, name: str) -> None:
        path = (ASSET_ROOT / name).resolve()
        if ASSET_ROOT.resolve() not in path.parents or not path.is_file():
            return self._json({"error": "asset not found"}, 404)
        self._file(path)

    def _file(self, path: Path) -> None:
        if not path.is_file():
            return self._json({"error": "file not found"}, 404)
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("content-type", CONTENT_TYPES.get(path.suffix, "application/octet-stream"))
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt: str, *args) -> None:  # quieter local server
        print(f"{self.address_string()} - {fmt % args}")


def main(host: str = "127.0.0.1", port: int = 8000) -> None:
    print(f"Holdem server: http://{host}:{port}")
    ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    main()
