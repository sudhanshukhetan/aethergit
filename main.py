"""Main entrypoint for Vercel / serverless runtimes."""

from http.server import BaseHTTPRequestHandler
from pathlib import Path

HTML_FILE = Path(__file__).resolve().parent / "index.html"


def app(environ, start_response):
    data = HTML_FILE.read_bytes() if HTML_FILE.exists() else b"AetherGit Decision Intelligence Online"
    start_response("200 OK", [
        ("Content-Type", "text/html; charset=utf-8"),
        ("Content-Length", str(len(data)))
    ])
    return [data]


application = app


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        data = HTML_FILE.read_bytes() if HTML_FILE.exists() else b"AetherGit Decision Intelligence Online"
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
