from __future__ import annotations

import datetime as dt
import json
import socket
import time
from typing import Any, Dict, Optional
from urllib.error import URLError
from urllib.request import Request, urlopen


def emit_syslog_json(
    event: Dict[str, Any],
    *,
    host: Optional[str] = None,
    port: int = 514,
    tag: str = "codex-usage-profiler",
    protocol: str = "tcp",
    timeout: float = 2.0,
) -> bool:
    if not host:
        return False
    payload = json.dumps(event, sort_keys=True, separators=(",", ":"))
    now = dt.datetime.now().strftime("%b %d %H:%M:%S")
    hostname = socket.gethostname().split(".")[0]
    message = f"<14>{now} {hostname} {tag}: {payload}\n".encode("utf-8", errors="replace")
    sock_type = socket.SOCK_DGRAM if protocol == "udp" else socket.SOCK_STREAM
    try:
        with socket.socket(socket.AF_INET, sock_type) as sock:
            sock.settimeout(timeout)
            if sock_type == socket.SOCK_DGRAM:
                sock.sendto(message, (host, port))
            else:
                sock.connect((host, port))
                sock.sendall(message)
        return True
    except OSError:
        return False


def emit_loki_json(
    event: Dict[str, Any],
    *,
    url: Optional[str] = None,
    labels: Optional[Dict[str, str]] = None,
    timeout: float = 2.0,
) -> bool:
    if not url:
        return False
    stream_labels = {"job": "codex-usage-profiler"}
    stream_labels.update({str(k): str(v) for k, v in (labels or {}).items() if v is not None})
    payload = {
        "streams": [
            {
                "stream": stream_labels,
                "values": [
                    [
                        str(time.time_ns()),
                        json.dumps(event, sort_keys=True, separators=(",", ":")),
                    ]
                ],
            }
        ]
    }
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            response.read()
        return True
    except (OSError, URLError):
        return False
