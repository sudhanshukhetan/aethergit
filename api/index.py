"""Vercel Serverless Entrypoint for AetherGit.

Standard Library only: exports 'handler' (BaseHTTPRequestHandler) and 'app' (WSGI callable).
"""

from http.server import BaseHTTPRequestHandler
from pathlib import Path

INDEX_PATH = Path(__file__).resolve().parent.parent / "index.html"


class handler(BaseHTTPRequestHandler):
    """Vercel native BaseHTTPRequestHandler entrypoint."""

    def do_GET(self):
        if INDEX_PATH.exists():
            content = INDEX_PATH.read_bytes()
        else:
            content = b"<!DOCTYPE html><html><body><h1>AetherGit</h1></body></html>"

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


def app(environ, start_response):
    """Standard WSGI entrypoint callable."""
    if INDEX_PATH.exists():
        content = INDEX_PATH.read_bytes()
    else:
        content = b"<!DOCTYPE html><html><body><h1>AetherGit</h1></body></html>"

    status = "200 OK"
    response_headers = [
        ("Content-Type", "text/html; charset=utf-8"),
        ("Content-Length", str(len(content))),
    ]
    start_response(status, response_headers)
    return [content]


# Additional common aliases for platform flexibility
application = app
