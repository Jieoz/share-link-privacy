#!/usr/bin/env python3
"""Share Link Privacy — local server (stdlib only).

Endpoints:
  GET  /           single-page UI
  POST /api/parse  {"url": "..."}  → ParseResult JSON
  GET  /api/health
  GET  /api/platforms
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from parsers import parse_share_url  # noqa: E402
from parsers.registry import supported_platforms  # noqa: E402

STATIC = ROOT / "static"
MAX_BODY = 32_000


class Handler(BaseHTTPRequestHandler):
    server_version = "ShareLinkPrivacy/1.0"

    def log_message(self, format: str, *args) -> None:  # noqa: A003 — stdlib signature
        sys.stderr.write("%s - %s\n" % (self.address_string(), format % args))

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _file(self, path: Path, content_type: str) -> None:
        if not path.is_file():
            self.send_error(404, "Not Found")
            return
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self._cors()
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path

        if path in {"/", "/index.html"}:
            self._file(STATIC / "index.html", "text/html; charset=utf-8")
            return
        if path == "/api/health":
            self._json(200, {"ok": True, "service": "share-link-privacy"})
            return
        if path == "/api/platforms":
            self._json(200, {"ok": True, "platforms": supported_platforms()})
            return
        if path == "/api/parse":
            # Convenience GET for manual debugging only.
            qs = parse_qs(parsed.query)
            url = (qs.get("url") or [""])[0]
            result = parse_share_url(url, expand=True, enrich=False)
            self._json(200, result.to_dict())
            return
        if path.startswith("/static/"):
            rel = path[len("/static/") :]
            if ".." in rel or rel.startswith("/"):
                self.send_error(400, "Bad path")
                return
            ctype = "application/octet-stream"
            if rel.endswith(".css"):
                ctype = "text/css; charset=utf-8"
            elif rel.endswith(".js"):
                ctype = "application/javascript; charset=utf-8"
            elif rel.endswith(".svg"):
                ctype = "image/svg+xml"
            self._file(STATIC / rel, ctype)
            return

        self.send_error(404, "Not Found")

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path != "/api/parse":
            self.send_error(404, "Not Found")
            return

        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > MAX_BODY:
            self._json(400, {"ok": False, "msg": "请求体无效或过大"})
            return
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._json(400, {"ok": False, "msg": "JSON 解析失败"})
            return

        # Accept several common shapes.
        url = ""
        if isinstance(payload, dict):
            nested = payload.get("data")
            data = nested if isinstance(nested, dict) else {}
            url = (
                payload.get("url")
                or payload.get("link")
                or data.get("url")
                or data.get("link")
                or ""
            )
        if not isinstance(url, str):
            url = str(url)

        # Optional flags (default safe for public demo).
        enrich = True
        expand = True
        if isinstance(payload, dict):
            if "enrich" in payload:
                enrich = bool(payload["enrich"])
            if "expand" in payload:
                expand = bool(payload["expand"])

        try:
            result = parse_share_url(url, expand=expand, enrich=enrich)
        except Exception as exc:  # noqa: BLE001 — return controlled error to client
            self._json(200, {"ok": False, "msg": f"解析出错：{exc.__class__.__name__}"})
            return
        self._json(200, result.to_dict())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Share Link Privacy server")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8787)
    args = ap.parse_args(argv)
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Share Link Privacy on http://{args.host}:{args.port}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nbye", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
