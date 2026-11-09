"""The local HTTP server for the network problems: a fixed 64 KB body after a 2 ms delay.

It runs in its own process, outside every tool's process tree. The body is the same bytes in
every run, so network problems have stable checksums.
"""

from __future__ import annotations

import random
import socket
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PAYLOAD = random.Random(0).randbytes(64 * 1024)
DELAY = 0.002


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def do_GET(self) -> None:
        time.sleep(DELAY)
        self.send_response(200)
        self.send_header("Content-Length", str(len(PAYLOAD)))
        self.end_headers()
        self.wfile.write(PAYLOAD)

    def log_message(self, format: str, *args: object) -> None:
        pass


def serve(port: int) -> None:
    ThreadingHTTPServer.request_queue_size = 256
    ThreadingHTTPServer.daemon_threads = True
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def start() -> tuple[subprocess.Popen, int]:
    """Start the server in a child process and wait until it accepts connections."""
    port = free_port()
    proc = subprocess.Popen([sys.executable, "-m", "nbbench.server", str(port)])
    deadline = time.time() + 10
    while time.time() < deadline:
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
            return proc, port
        except OSError:
            time.sleep(0.05)
    proc.kill()
    raise RuntimeError("the local HTTP server did not start")


if __name__ == "__main__":
    serve(int(sys.argv[1]))
