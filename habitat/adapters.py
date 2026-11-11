"""Integration boundaries for Habitat runtimes and evidence sources.

Adapters are intentionally small and stdlib-only. They let Habitat verify claims
against systems outside its own process without making those systems part of the
core domain model.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import ipaddress
import json
import os
from pathlib import Path
import re
import shlex
import socket
import subprocess
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

MAX_EVIDENCE_RESPONSE_BYTES = 1_048_576
_SAFE_GITHUB_NAME = re.compile(r"^[A-Za-z0-9_.-]+$")


class _NoRedirectHandler(HTTPRedirectHandler):
    """Do not silently turn an evidence URL into an attacker-chosen URL."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise URLError("redirect_not_allowed")


_NO_REDIRECT_OPENER = build_opener(_NoRedirectHandler)


def _validate_http_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("unsupported_evidence_url_scheme")
    if not parsed.hostname:
        raise ValueError("evidence_url_missing_host")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("evidence_url_credentials_not_allowed")

    # Evidence URLs are configuration, but a compromised/untrusted configuration
    # must not turn the adapter into an easy SSRF primitive. Resolve every address
    # before opening the URL and reject any hostname that can resolve to a local,
    # private, link-local, loopback, multicast, reserved, or unspecified address.
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)}
    except socket.gaierror as exc:
        raise ValueError("evidence_url_host_unresolvable") from exc
    if not addresses:
        raise ValueError("evidence_url_host_unresolvable")
    for address in addresses:
        try:
            ip = ipaddress.ip_address(address)
        except ValueError as exc:
            raise ValueError("evidence_url_invalid_address") from exc
        if not ip.is_global:
            raise ValueError("evidence_url_private_address")


def _read_limited(response) -> bytes:
    content_length = response.headers.get("Content-Length")
    if content_length:
        try:
            if int(content_length) > MAX_EVIDENCE_RESPONSE_BYTES:
                raise ValueError("evidence_response_too_large")
        except ValueError:
            if content_length != "0":
                raise ValueError("invalid_content_length")
    data = response.read(MAX_EVIDENCE_RESPONSE_BYTES + 1)
    if len(data) > MAX_EVIDENCE_RESPONSE_BYTES:
        raise ValueError("evidence_response_too_large")
    return data


@dataclass
class ExecutionResult:
    ok: bool
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None


class JobAdapter(Protocol):
    def execute(self, command: str, timeout: int = 300) -> ExecutionResult: ...


class ShellAdapter:
    """Local command adapter. Safe argv execution is the default; shell mode is explicit."""

    def __init__(self, allow_shell: bool = False):
        self.allow_shell = allow_shell

    def execute(self, command: str, timeout: int = 300) -> ExecutionResult:
        try:
            argv = command if self.allow_shell else shlex.split(command)
            p = subprocess.run(argv, shell=self.allow_shell, capture_output=True, text=True, timeout=timeout)
            return ExecutionResult(p.returncode == 0, p.stdout[-4000:], p.stderr[-4000:], p.returncode)
        except subprocess.TimeoutExpired as exc:
            return ExecutionResult(False, str(exc.stdout or "")[-4000:], "command timed out", None)
        except Exception as exc:
            return ExecutionResult(False, "", str(exc)[-4000:], None)


@dataclass
class Evidence:
    """Normalized evidence returned by an external system."""

    source: str
    observed: bool
    status: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class EvidenceAdapter(Protocol):
    def observe(self, query: str) -> Evidence: ...


class JSONFileEvidenceAdapter:
    """Read deterministic evidence from a local JSON document."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def observe(self, query: str) -> Evidence:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            value: Any = payload
            for part in query.split(".") if query else []:
                if not isinstance(value, dict) or part not in value:
                    return Evidence(str(self.path), False, error=f"path_not_found:{query}")
                value = value[part]
            if isinstance(value, dict):
                return Evidence(str(self.path), True, value.get("status"), value)
            return Evidence(str(self.path), True, str(value) if value is not None else None, {"value": value})
        except Exception as exc:
            return Evidence(str(self.path), False, error=str(exc))


class HTTPJSONEvidenceAdapter:
    """Fetch bounded JSON evidence from a fixed HTTP endpoint without redirects."""

    def __init__(self, base_url: str, token_env: str | None = None, timeout: int = 15):
        _validate_http_url(base_url)
        if timeout <= 0 or timeout > 300:
            raise ValueError("invalid_evidence_timeout")
        self.base_url = base_url.rstrip("/")
        self.token_env = token_env
        self.timeout = timeout

    def observe(self, query: str) -> Evidence:
        req = Request(self.base_url, headers={"Accept": "application/json", "User-Agent": "Habitat/1.0"})
        token = os.getenv(self.token_env) if self.token_env else None
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        try:
            with _NO_REDIRECT_OPENER.open(req, timeout=self.timeout) as response:
                payload = json.loads(_read_limited(response).decode("utf-8"), parse_constant=lambda value: (_ for _ in ()).throw(ValueError("invalid_json_constant")))
            value: Any = payload
            for part in query.split(".") if query else []:
                if not isinstance(value, dict) or part not in value:
                    return Evidence(self.base_url, False, error=f"path_not_found:{query}")
                value = value[part]
            if isinstance(value, dict):
                return Evidence(self.base_url, True, value.get("status"), value)
            return Evidence(self.base_url, True, str(value) if value is not None else None, {"value": value})
        except HTTPError as exc:
            return Evidence(self.base_url, False, error=f"http_{exc.code}")
        except (URLError, TimeoutError, ValueError) as exc:
            return Evidence(self.base_url, False, error=str(exc))


class GitHubIssueEvidenceAdapter:
    """Verify that a GitHub issue exists. Query format: owner/repo#number."""

    def __init__(self, token_env: str = "GITHUB_TOKEN", timeout: int = 15):
        if timeout <= 0 or timeout > 300:
            raise ValueError("invalid_evidence_timeout")
        self.token_env = token_env
        self.timeout = timeout

    def observe(self, query: str) -> Evidence:
        try:
            repo, number = query.rsplit("#", 1)
            owner, name = repo.split("/", 1)
            if not _SAFE_GITHUB_NAME.fullmatch(owner) or not _SAFE_GITHUB_NAME.fullmatch(name):
                raise ValueError("invalid_github_repository")
            issue_number = int(number)
            if issue_number <= 0:
                raise ValueError("invalid_github_issue_number")
            url = f"https://api.github.com/repos/{owner}/{name}/issues/{issue_number}"
            req = Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "Habitat/1.0"})
            token = os.getenv(self.token_env)
            if token:
                req.add_header("Authorization", f"Bearer {token}")
            with _NO_REDIRECT_OPENER.open(req, timeout=self.timeout) as response:
                payload = json.loads(_read_limited(response).decode("utf-8"), parse_constant=lambda value: (_ for _ in ()).throw(ValueError("invalid_json_constant")))
            return Evidence("github", True, "ok", {"number": payload.get("number"), "state": payload.get("state"), "title": payload.get("title"), "url": payload.get("html_url")})
        except HTTPError as exc:
            if exc.code == 404:
                return Evidence("github", False, error="issue_not_found")
            return Evidence("github", False, error=f"http_{exc.code}")
        except (ValueError, URLError, TimeoutError) as exc:
            return Evidence("github", False, error=str(exc))
