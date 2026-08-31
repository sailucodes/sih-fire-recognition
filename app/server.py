import os
import sys
import json
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import urlparse, parse_qs
from app.api.router import router

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "app" / "static"

SWAGGER_HTML = """<!DOCTYPE html>
<html>
<head>
  <title>AeroThermal AI - Swagger API Documentation</title>
  <link rel="stylesheet" type="text/css" href="https://unpkg.com/swagger-ui-dist@5.11.0/swagger-ui.css">
  <style>body { margin: 0; background: #fafafa; }</style>
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://unpkg.com/swagger-ui-dist@5.11.0/swagger-ui-bundle.js"></script>
  <script>
    window.onload = function() {
      SwaggerUIBundle({
        url: "/api/v1/openapi.json",
        dom_id: '#swagger-ui',
        deepLinking: true,
        presets: [SwaggerUIBundle.presets.apis],
        layout: "BaseLayout"
      });
    };
  </script>
</body>
</html>
"""

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

class AeroThermalHTTPHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query_params = parse_qs(parsed.query)

        # 1. Root / Map Visualizer
        if path in ["", "/", "/map"]:
            self._serve_static_html("index.html")
            return

        # 2. Interactive Swagger UI
        elif path == "/docs":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(SWAGGER_HTML.encode("utf-8"))
            return

        # 3. API Dispatch
        status, headers, content = router.handle_request("GET", path, query_params, b"")
        self._send_custom_response(status, headers, content)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query_params = parse_qs(parsed.query)

        content_len = int(self.headers.get("Content-Length", 0))
        body_data = self.rfile.read(content_len) if content_len > 0 else b""

        status, headers, content = router.handle_request("POST", path, query_params, body_data)
        self._send_custom_response(status, headers, content)

    def _serve_static_html(self, filename: str):
        filepath = STATIC_DIR / filename
        if os.path.exists(filepath):
            with open(filepath, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(data)
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Static file not found")

    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def _send_custom_response(self, status: int, headers: dict, content: bytes):
        self.send_response(status)
        for k, v in headers.items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format, *args):
        # Custom clean logging
        print(f"[API] {self.command} {self.path} - {args[1] if len(args)>1 else ''}")

def start_server(host: str = "0.0.0.0", port: int = 8000):
    server = ThreadedHTTPServer((host, port), AeroThermalHTTPHandler)
    print("=" * 70)
    print(f"[FIRE] AeroThermal AI Geospatial Backend Server is LIVE!")
    print(f"[MAP] Interactive Map Visualizer: http://localhost:{port}/")
    print(f"[DOCS] Swagger API Documentation:  http://localhost:{port}/docs")
    print(f"[GIS] GeoJSON API Endpoint:       http://localhost:{port}/api/v1/sources/geojson")
    print("=" * 70)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
        server.server_close()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    start_server(port=port)