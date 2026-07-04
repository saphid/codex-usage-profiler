from __future__ import annotations

import argparse
import json
import mimetypes
import socket
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from typing import Optional
from urllib.parse import unquote, urlparse

from .syslog_util import emit_loki_json, emit_syslog_json


STATIC_PACKAGE = "codex_usage_profiler"
STATIC_DIR = "dashboard_static"


def _static_root():
    return resources.files(STATIC_PACKAGE).joinpath(STATIC_DIR)


class DashboardHandler(BaseHTTPRequestHandler):
    report_path: Path
    syslog_host: Optional[str] = None
    syslog_port: int = 514
    loki_url: Optional[str] = None

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        if path == "/api/report":
            self._serve_report()
            return
        if path == "/healthz":
            self._send_bytes(b"ok\n", "text/plain; charset=utf-8")
            return
        if path in ("", "/"):
            path = "/index.html"
        self._serve_static(path.lstrip("/"))

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        message = format % args
        sys.stderr.write("dashboard: " + message + "\n")
        emit_syslog_json(
            {
                "event": "dashboard_access",
                "host": socket.gethostname(),
                "client": self.client_address[0] if self.client_address else "unknown",
                "request": getattr(self, "requestline", ""),
                "message": message,
            },
            host=self.syslog_host,
            port=self.syslog_port,
            tag="codex-usage-dashboard",
        )
        emit_loki_json(
            {
                "event": "dashboard_access",
                "host": socket.gethostname(),
                "client": self.client_address[0] if self.client_address else "unknown",
                "request": getattr(self, "requestline", ""),
                "message": message,
            },
            url=self.loki_url,
            labels={"service": "dashboard", "host": socket.gethostname()},
        )

    def _serve_report(self) -> None:
        try:
            data = self.report_path.read_bytes()
            json.loads(data.decode("utf-8"))
        except FileNotFoundError:
            self._send_error(404, f"Report not found: {self.report_path}")
            return
        except json.JSONDecodeError as exc:
            self._send_error(500, f"Report is not valid JSON: {exc}")
            return
        self._send_bytes(data, "application/json; charset=utf-8")

    def _serve_static(self, relative: str) -> None:
        if "/" in relative:
            parts = [part for part in relative.split("/") if part and part not in (".", "..")]
            relative = "/".join(parts)
        if not relative or relative.startswith("../") or "/../" in relative:
            self._send_error(400, "Invalid path")
            return
        try:
            resource = _static_root().joinpath(relative)
            data = resource.read_bytes()
        except FileNotFoundError:
            self._send_error(404, "Not found")
            return
        content_type = mimetypes.guess_type(relative)[0] or "application/octet-stream"
        if content_type.startswith("text/") or relative.endswith(".js"):
            content_type += "; charset=utf-8"
        self._send_bytes(data, content_type)

    def _send_bytes(self, data: bytes, content_type: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _send_error(self, status: int, message: str) -> None:
        data = json.dumps({"error": message}).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def make_server(
    report_path: str | Path,
    host: str = "127.0.0.1",
    port: int = 8765,
    syslog_host: Optional[str] = None,
    syslog_port: int = 514,
    loki_url: Optional[str] = None,
) -> ThreadingHTTPServer:
    report = Path(report_path).expanduser().resolve()

    class BoundDashboardHandler(DashboardHandler):
        pass

    BoundDashboardHandler.report_path = report
    BoundDashboardHandler.syslog_host = syslog_host
    BoundDashboardHandler.syslog_port = syslog_port
    BoundDashboardHandler.loki_url = loki_url
    return ThreadingHTTPServer((host, port), BoundDashboardHandler)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="codex-usage-dashboard",
        description="Serve a local dashboard for a Codex Usage Profiler JSON report.",
    )
    parser.add_argument("--report", default="samples/demo-report.json", help="Profiler JSON report to serve")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host. Use 0.0.0.0 for Tailscale/LAN access")
    parser.add_argument("--port", type=int, default=8765, help="Bind port")
    parser.add_argument("--syslog-host", help="Optional syslog host for dashboard access events")
    parser.add_argument("--syslog-port", type=int, default=514)
    parser.add_argument("--loki-url", help="Optional Loki push API URL for dashboard access events")
    args = parser.parse_args(argv)

    server = make_server(args.report, args.host, args.port, args.syslog_host, args.syslog_port, args.loki_url)
    bound_host, bound_port = server.server_address
    print(f"Codex Usage Profiler dashboard: http://{bound_host}:{bound_port}/")
    print(f"Report: {Path(args.report).expanduser().resolve()}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping dashboard")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
