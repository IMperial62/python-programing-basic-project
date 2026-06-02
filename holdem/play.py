from __future__ import annotations

import socket
import threading
import webbrowser
from http.server import ThreadingHTTPServer

from .server import Handler


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def main() -> None:
    port = free_port()
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"Holdem web app opened: {url}")
    print("Press Ctrl+C to stop.")
    webbrowser.open(url)
    try:
        thread.join()
    except KeyboardInterrupt:
        server.shutdown()
        print("\nStopped.")


if __name__ == "__main__":
    main()
