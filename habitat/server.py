"""Local-first Habitat HTTP API.

Loopback listeners may be used without an HTTP auth header. Non-loopback
listeners require the configured server secret as a bearer credential for
every request. Remote deployments should additionally use TLS at the network
boundary because bearer credentials and event secrets are transport secrets.
"""
from __future__ import annotations

from collections import defaultdict
import hmac
import ipaddress
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from .events import ingest_event, MAX_EVENT_BYTES
from .store import Store
from .generate import render_dashboard, render_landing
from .proof_ui import render_proof_inspector
from .verify_api import proof_status, verify_and_prove

MAX_HTTP_CONNECTIONS = 64


class _AuthRateLimiter:
    """Bound repeated remote authentication failures without affecting localhost."""
    def __init__(self, max_failures=5, window_seconds=60, max_keys=4096):
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self.max_keys = max_keys
        self._failures = defaultdict(list)
        self._lock = threading.Lock()

    def _prune(self, key, now):
        cutoff = now - self.window_seconds
        entries = [stamp for stamp in self._failures.get(key, []) if stamp > cutoff]
        if entries:
            self._failures[key] = entries
        else:
            self._failures.pop(key, None)
        return entries

    def blocked(self, key, now=None):
        now = time.monotonic() if now is None else now
        with self._lock:
            return len(self._prune(key, now)) >= self.max_failures

    def record_failure(self, key, now=None):
        now = time.monotonic() if now is None else now
        with self._lock:
            entries = self._prune(key, now)
            entries.append(now)
            self._failures[key] = entries
            if len(self._failures) > self.max_keys:
                oldest_key = min(self._failures, key=lambda candidate: self._failures[candidate][-1])
                if oldest_key != key:
                    self._failures.pop(oldest_key, None)
            return len(entries) >= self.max_failures

    def clear(self, key):
        with self._lock:
            self._failures.pop(key, None)


class HabitatHTTPServer(ThreadingHTTPServer):
    """Threaded HTTP server with a hard cap on active request threads."""
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, server_address, handler_cls, max_connections=MAX_HTTP_CONNECTIONS):
        if max_connections <= 0:
            raise ValueError("max_connections must be positive")
        self._connection_slots = threading.BoundedSemaphore(max_connections)
        super().__init__(server_address, handler_cls)

    def process_request(self, request, client_address):
        if not self._connection_slots.acquire(blocking=False):
            request.close()
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self._connection_slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._connection_slots.release()


def _is_loopback_host(host: str) -> bool:
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return host.lower() in {"localhost", "ip6-localhost"}


def make_handler(db_path, secret, require_signature=True, protect_remote=True):
    limiter = _AuthRateLimiter()

    class Handler(BaseHTTPRequestHandler):
        server_version = "Habitat/1.3"
        protocol_version = "HTTP/1.1"

        def setup(self):
            super().setup()
            self.connection.settimeout(10)

        def _remote_protected(self) -> bool:
            if not protect_remote:
                return False
            bound = getattr(self.server, "server_address", ("127.0.0.1", 0))[0]
            return not _is_loopback_host(str(bound))

        def _client_key(self, kind):
            peer = getattr(self, "client_address", ("unknown", 0))
            return kind, str(peer[0])

        def _auth_throttled(self, kind):
            return limiter.blocked(self._client_key(kind))

        def _auth_failed(self, kind):
            return limiter.record_failure(self._client_key(kind))

        def _auth_succeeded(self, kind):
            limiter.clear(self._client_key(kind))

        def _send_rate_limited(self):
            self._send(429, {"error": "authentication_rate_limited"}, headers={"Retry-After": "60"})

        def _authorized_read(self):
            if not self._remote_protected():
                return True
            if self._auth_throttled("server"):
                return None
            supplied = self.headers.get("Authorization", "")
            if not secret or not supplied.startswith("Bearer "):
                self._auth_failed("server")
                return False
            valid = hmac.compare_digest(supplied[7:].strip(), secret)
            if not valid:
                self._auth_failed("server")
                return False
            self._auth_succeeded("server")
            return True

        def _send(self, code, payload, headers=None):
            raw = json.dumps(payload, default=str).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            for name, value in (headers or {}).items():
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(raw)

        def _send_forbidden(self):
            self._send(401, {"error": "authentication_required"})

        def do_GET(self):
            authorized = self._authorized_read()
            if authorized is None:
                self._send_rate_limited()
                return
            if not authorized:
                self._send_forbidden()
                return
            path = urlparse(self.path).path
            s = Store(db_path)
            try:
                if path == "/":
                    html = render_landing(s.habitat().name)
                    raw = html.encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(raw)))
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'; connect-src 'self'")
                    self.send_header("X-Content-Type-Options", "nosniff")
                    self.send_header("Referrer-Policy", "no-referrer")
                    self.end_headers()
                    self.wfile.write(raw)
                elif path == "/dashboard":
                    html = render_dashboard(s.habitat(), s.jobs(), s.signals(), s.actions(), s.habitat().name, s.claims())
                    raw = html.encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(raw)))
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'")
                    self.send_header("X-Content-Type-Options", "nosniff")
                    self.send_header("Referrer-Policy", "no-referrer")
                    self.end_headers()
                    self.wfile.write(raw)
                elif path.startswith("/dashboard/claims/"):
                    claim_id = path[len("/dashboard/claims/"):].strip("/")
                    if not claim_id or "/" in claim_id:
                        self._send(400, {"error": "invalid_claim_id"})
                    else:
                        html = render_proof_inspector(proof_status(s, claim_id), s.habitat().name)
                        raw = html.encode("utf-8")
                        self.send_response(200)
                        self.send_header("Content-Type", "text/html; charset=utf-8")
                        self.send_header("Content-Length", str(len(raw)))
                        self.send_header("Cache-Control", "no-store")
                        self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'")
                        self.send_header("X-Content-Type-Options", "nosniff")
                        self.send_header("Referrer-Policy", "no-referrer")
                        self.end_headers()
                        self.wfile.write(raw)
                elif path == "/v1/status":
                    h = s.habitat()
                    self._send(200, {"id": h.id, "name": h.name, "status": h.status, "model": h.model, "jobs": len(s.jobs()), "active_signals": len(s.active_signals()), "agents": len(s.agents())})
                elif path == "/v1/claims":
                    self._send(200, [c.__dict__ for c in s.claims()])
                elif path.startswith("/v1/claims/") and path.endswith("/proof"):
                    claim_id = path[len("/v1/claims/"):-len("/proof")].strip("/")
                    if not claim_id:
                        self._send(400, {"error": "missing_claim_id"})
                    else:
                        self._send(200, proof_status(s, claim_id))
                elif path.startswith("/v1/claims/") and path.endswith("/verify"):
                    claim_id = path[len("/v1/claims/"):-len("/verify")].strip("/")
                    if not claim_id:
                        self._send(400, {"error": "missing_claim_id"})
                    else:
                        self._send(200, verify_and_prove(s, claim_id))
                elif path == "/v1/signals":
                    self._send(200, [x.__dict__ for x in s.active_signals()])
                elif path == "/v1/events":
                    self._send(200, s.events())
                elif path == "/v1/actions":
                    self._send(200, [x.__dict__ for x in s.actions()])
                elif path == "/v1/agents":
                    self._send(200, s.agents())
                elif path == "/healthz":
                    self._send(200, {"ok": True})
                else:
                    self._send(404, {"error": "not_found"})
            except KeyError:
                self._send(404, {"error": "claim_not_found"})
            except RuntimeError as exc:
                self._send(503, {"error": str(exc)})
            finally:
                s.close()

        def do_POST(self):
            if urlparse(self.path).path != "/v1/events":
                self._send(404, {"error": "not_found"})
                return
            if self._remote_protected():
                authorized = self._authorized_read()
                if authorized is None:
                    self._send_rate_limited()
                    return
                if not authorized:
                    self._send_forbidden()
                    return
            if self._remote_protected() and self._auth_throttled("agent"):
                self._send_rate_limited()
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self._send(400, {"error": "invalid_content_length"})
                return
            if length <= 0 or length > MAX_EVENT_BYTES:
                self._send(413, {"error": "event_too_large"})
                return
            body = self.rfile.read(length)
            if len(body) != length:
                self._send(400, {"error": "incomplete_request_body"})
                return
            sig = self.headers.get("X-Habitat-Signature")
            agent_id = self.headers.get("X-Habitat-Agent")
            agent_secret = self.headers.get("X-Habitat-Agent-Secret")
            s = Store(db_path)
            try:
                result = ingest_event(s, body, sig, secret, require_signature, agent_id, agent_secret)
                if self._remote_protected() and agent_secret:
                    self._auth_succeeded("agent")
                self._send(200 if result.get("duplicate") else 202, result)
            except PermissionError as exc:
                if self._remote_protected() and agent_secret:
                    self._auth_failed("agent")
                    if self._auth_throttled("agent"):
                        self._send_rate_limited()
                        return
                self._send(401, {"error": str(exc)})
            except ValueError as exc:
                self._send(400, {"error": str(exc)})
            except RuntimeError as exc:
                self._send(503, {"error": str(exc)})
            finally:
                s.close()

        def log_message(self, *args):
            return

    return Handler


def serve(db_path, host="127.0.0.1", port=8787, secret=None, require_signature=True):
    if not _is_loopback_host(host) and not secret:
        raise ValueError("non-loopback listeners require a server secret")

    httpd = HabitatHTTPServer((host, port), make_handler(db_path, secret, require_signature, protect_remote=True))
    print(f"Habitat API listening on http://{host}:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
