"""Temporarily review the panel through loopback, without exposing credentials.

Use an SSH loopback tunnel to this port. A native session retains an existing
business editor's permissions; the proxy accepts only read operations and is
removed with its session on termination. It never changes users or passwords.
"""
import argparse
import configparser
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import signal
import subprocess
import time
from urllib.parse import urlsplit


READ_METHODS = {
    "get_management_dashboard", "read", "web_read", "search_read", "web_search_read",
    "get_views", "get_view", "fields_get", "name_search", "search_count",
    "check_access_rights", "check_access", "has_group", "has_groups", "context_get",
    "systray_get_activities", "get_discuss_settings", "get_formview_action",
}
READ_POSTS = {"/web/action/load", "/web/session/get_session_info", "/mail/data",
              "/bus/has_missed_notifications", "/web/webclient/version_info"}


def is_read_request(path, body):
    path = urlsplit(path).path
    if path in READ_POSTS:
        return True
    if not path.startswith("/web/dataset/call_kw"):
        return False
    try:
        return json.loads(body).get("params", {}).get("method") in READ_METHODS
    except (ValueError, AttributeError):
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("environment", choices=("development", "cerro", "qa-cerro"))
    parser.add_argument("--port", type=int, default=18228)
    parser.add_argument("--minutes", type=int, default=25)
    args = parser.parse_args()
    assert os.geteuid() == 0 and 1024 <= args.port <= 65535 and 1 <= args.minutes <= 30
    root = Path(__file__).resolve().parent
    target = json.loads((root / "environments.json").read_text())["environments"][args.environment]
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.read(target["config"])
    assert cfg["options"]["db_name"] == target["database"]
    user = subprocess.check_output(["systemctl", "show", "--value", "--property=User", target["service"]], text=True).strip()
    proof = Path("/tmp/t201-browser-panel-%s-%s.json" % (args.environment, os.getpid()))
    variables = ["T201_BROWSER_PROOF=" + str(proof)]
    command = ["sudo", "-u", user, "env", *variables]
    odoo = ["/usr/bin/python3.10", "/opt/odoo18/odoo-bin", "shell", "-c", target["config"],
            "-d", target["database"], "--no-http", "--workers=0", "--max-cron-threads=0", "--log-level=error"]
    script = "import sys\nsys.path.insert(0," + repr(str(root)) + ")\n" + (root / "t201_browser_session.py").read_text()

    def session(cleanup=False):
        result = subprocess.run(command + (["T201_CLEANUP=1"] if cleanup else []) + odoo,
                                input=script, text=True, capture_output=True)
        assert result.returncode == 0 and "T201_BROWSER_SESSION_" in result.stdout, result.stderr[-1200:]

    server = None
    try:
        session()
        auth = json.loads(proof.read_text())
        assert auth["host"] == urlsplit(target["url"]).hostname

        class Proxy(BaseHTTPRequestHandler):
            def log_message(self, *unused):
                pass

            def forward(self):
                length = int(self.headers.get("Content-Length", 0))
                if length > 2_000_000:
                    self.send_error(413)
                    return
                body = self.rfile.read(length) if length else b""
                # Webclient boot asks for an optional IoT channel. The native
                # method can create one, so keep IoT disabled in this read-only
                # review instead of creating a channel or changing its config.
                if urlsplit(self.path).path == "/web/dataset/call_kw/iot.channel/get_iot_channel":
                    payload = json.loads(body)
                    data = json.dumps({"jsonrpc": "2.0", "id": payload.get("id"), "result": ""}).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                    return
                if self.command == "POST" and not is_read_request(self.path, body):
                    print("MANAGEMENT_PANEL_REVIEW_BLOCKED " + urlsplit(self.path).path, flush=True)
                    self.send_error(403, "Read-only panel review")
                    return
                path = urlsplit(self.path).path
                if self.command == "GET" and not (
                    path in ("/web", "/odoo") or path.startswith(("/odoo/", "/web/assets/",
                    "/web/image", "/web/content/", "/web/webclient/", "/web/binary/company_logo",
                    "/bus/websocket_worker_bundle"))
                    or "/static/" in path
                ):
                    self.send_error(403, "Read-only panel review")
                    return
                if urlsplit(self.path).path.startswith(("/websocket", "/web/login", "/web/database")):
                    self.send_error(403, "Read-only panel review")
                    return
                headers = {k: v for k, v in self.headers.items()
                           if k.lower() not in ("cookie", "host", "connection", "accept-encoding")}
                headers.update(Host=auth["host"], Cookie="session_id=" + auth["session_id"],
                               Connection="close", **{"X-Forwarded-Proto": "https"})
                connection = http.client.HTTPConnection("127.0.0.1", target["port"], timeout=90)
                try:
                    connection.request(self.command, self.path, body=body or None, headers=headers)
                    response = connection.getresponse()
                    data = response.read()
                    self.send_response(response.status)
                    for name, value in response.getheaders():
                        if name.lower() not in ("set-cookie", "content-length", "transfer-encoding", "connection"):
                            self.send_header(name, value)
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                finally:
                    connection.close()

            do_GET = forward
            do_POST = forward

        server = ThreadingHTTPServer(("127.0.0.1", args.port), Proxy)
        server.timeout = 1
        stopped = False

        def stop(*unused):
            nonlocal stopped
            stopped = True

        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        deadline = time.monotonic() + args.minutes * 60
        print("MANAGEMENT_PANEL_REVIEW_READY http://127.0.0.1:%s/odoo" % args.port, flush=True)
        while not stopped and time.monotonic() < deadline:
            server.handle_request()
    finally:
        if server:
            server.server_close()
        if proof.exists():
            session(cleanup=True)
        print("MANAGEMENT_PANEL_REVIEW_REMOVED", flush=True)


if __name__ == "__main__":
    main()
