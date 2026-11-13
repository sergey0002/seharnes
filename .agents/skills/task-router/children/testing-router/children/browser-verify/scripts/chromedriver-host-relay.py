#!/usr/bin/env python3
"""Loopback HTTP relay that rewrites Host for ChromeDriver 111+.

ChromeDriver rejects requests with a non-local Host header
("Rejecting request with non-local host: host.docker.internal:9515").
Docker on Docker Desktop reaches WSL only through host.docker.internal,
so the driver would reject every container request.

This relay listens on 127.0.0.1:9515, forwards to the driver on
127.0.0.1:9516 and replaces Host with 127.0.0.1:9516. Both ends are
loopback, so the driver keeps its own IP allowlist protections.

Usage: chromium-host-relay.py [--listen-port 9515] [--upstream-port 9516]
"""

import argparse
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class RelayHandler(BaseHTTPRequestHandler):
    # HTTP/1.0 forces a new connection per WebDriver command. With 1.1 the
    # php-webdriver curl client sometimes reused a socket the relay had
    # already closed and got "Empty reply from server".
    protocol_version = "HTTP/1.0"
    upstream_host = "127.0.0.1"
    upstream_port = 9516

    def _proxy(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None
        headers = {
            key: value
            for key, value in self.headers.items()
            if key.lower() not in ("host", "connection", "content-length", "transfer-encoding")
        }
        headers["Host"] = f"{self.upstream_host}:{self.upstream_port}"
        if body is not None:
            headers["Content-Length"] = str(len(body))

        conn = http.client.HTTPConnection(self.upstream_host, self.upstream_port, timeout=600)
        try:
            conn.request(self.command, self.path, body=body, headers=headers)
            response = conn.getresponse()
            data = response.read()
        except OSError as error:
            self.send_response(502)
            message = str(error).encode("utf-8")
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(message)))
            self.end_headers()
            self.wfile.write(message)
            return
        finally:
            conn.close()

        self.send_response(response.status, response.reason)
        for key, value in response.getheaders():
            if key.lower() in ("connection", "content-length", "transfer-encoding"):
                continue
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        if self.command != "HEAD":
            self.wfile.write(data)

    do_GET = do_POST = do_DELETE = do_PUT = do_PATCH = _proxy

    def log_message(self, *args):
        pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--listen-port", type=int, default=9515)
    parser.add_argument("--upstream-port", type=int, default=9516)
    args = parser.parse_args()
    RelayHandler.upstream_port = args.upstream_port
    server = ThreadingHTTPServer(("127.0.0.1", args.listen_port), RelayHandler)
    server.daemon_threads = True
    server.serve_forever()


if __name__ == "__main__":
    main()
