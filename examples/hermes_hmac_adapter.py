#!/usr/bin/env python3
"""Production-shaped Hermes → Habitat event/HMAC adapter.

Matches the real Hermes layout that agentscope already auto-detects:

  ~/.hermes/cron/jobs*          job definitions
  ~/.hermes/cron/executions.db  run history
  ~/.hermes/sessions            session activity

This adapter does two things:

1. After a consequential Hermes job finishes, POST a signed Habitat event
   (job.completed / job.failed) using the same HMAC scheme Habitat expects.
2. Optionally bind a claim and export a portable proof + tip file.

Secrets never appear on the command line. Use environment variables:

  HABITAT_AGENT_SECRET   — agent secret registered in Habitat
  HABITAT_WEBHOOK_SECRET — optional webhook secret if using that path
  HABITAT_URL            — default http://127.0.0.1:8787
  HABITAT_AGENT_ID       — registered agent id
  HABITAT_HABITAT_ID     — habitat id
  HABITAT_JOB_ID         — job id known to Habitat

Usage (from a Hermes post-action hook or cron wrapper):

  python examples/hermes_hmac_adapter.py \
    --run-id "$HERMES_RUN_ID" \
    --status ok \
    --claim "Hermes completed scheduled job X" \
    --prove
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Allow running from repo root without install
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from habitat.events import signature_for  # noqa: E402


MAX_RUN_ID_LENGTH = 256
MAX_CLAIM_LENGTH = 100000  # 100KB max claim
MAX_ERROR_LENGTH = 10000


def _env(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name, default)


def _validate_inputs(run_id: str, claim: str | None, error: str | None) -> list[str]:
    """Validate adapter inputs. Returns list of errors (empty if valid)."""
    errors = []
    
    if not run_id or not run_id.strip():
        errors.append("run_id cannot be empty")
    elif len(run_id) > MAX_RUN_ID_LENGTH:
        errors.append(f"run_id exceeds maximum length of {MAX_RUN_ID_LENGTH}")
    elif any(ord(c) < 32 for c in run_id):
        errors.append("run_id contains control characters")
    
    if claim is not None:
        if len(claim) > MAX_CLAIM_LENGTH:
            errors.append(f"claim exceeds maximum length of {MAX_CLAIM_LENGTH}")
        if "\x00" in claim:
            errors.append("claim contains null bytes")
    
    if error is not None:
        if len(error) > MAX_ERROR_LENGTH:
            errors.append(f"error exceeds maximum length of {MAX_ERROR_LENGTH}")
        if "\x00" in error:
            errors.append("error contains null bytes")
    
    return errors


def build_event(
    *,
    event_type: str,
    habitat_id: str,
    job_id: str,
    run_id: str,
    agent_id: str | None,
    error: str | None = None,
    claim: str | None = None,
) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    payload: dict = {
        "id": str(uuid.uuid4()),
        "type": event_type,
        "habitat_id": habitat_id,
        "job_id": job_id,
        "run_id": run_id,
        "correlation_id": run_id,
        "timestamp": now,
    }
    if agent_id:
        payload["agent_id"] = agent_id
    if error:
        payload["error"] = error
    if event_type == "claim.submitted" and claim:
        payload["claim"] = claim
        payload["expected_status"] = "ok"
        payload["action"] = "run_job"
    return payload


def post_signed(url: str, body: bytes, secret: str, agent_id: str | None = None) -> dict:
    sig = signature_for(secret, body)
    headers = {
        "Content-Type": "application/json",
        "X-Habitat-Signature": f"sha256={sig}",
    }
    if agent_id:
        headers["X-Habitat-Agent-Id"] = agent_id
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        raise SystemExit(f"Habitat HTTP {e.code}: {detail}") from e


def local_prove(run_id: str, claim_text: str, status: str, details: dict | None) -> dict:
    """Fallback when Habitat HTTP is not running: use in-process bridge."""
    from examples.hermes_bridge import record_and_prove

    return record_and_prove(
        run_id=run_id,
        action_name="run_job",
        claim_text=claim_text,
        status=status,
        details=details or {"source": "hermes_hmac_adapter"},
    )


def main() -> int:
    p = argparse.ArgumentParser(description="Hermes → Habitat HMAC event adapter")
    p.add_argument("--run-id", required=True, help="Hermes / OTel run or correlation id")
    p.add_argument("--status", choices=("ok", "failed"), default="ok")
    p.add_argument("--error", default=None, help="Error text when status=failed")
    p.add_argument("--claim", default=None, help="Optional claim text to submit after the job event")
    p.add_argument("--prove", action="store_true", help="Also export portable proof + tip (local path)")
    p.add_argument("--local-only", action="store_true", help="Skip HTTP; use in-process bridge only")
    p.add_argument("--url", default=_env("HABITAT_URL", "http://127.0.0.1:8787"))
    args = p.parse_args()

    # Validate inputs
    validation_errors = _validate_inputs(args.run_id, args.claim, args.error)
    if validation_errors:
        result = {"error": "input_validation_failed", "details": validation_errors}
        print(json.dumps(result, indent=2))
        return 1

    habitat_id = _env("HABITAT_HABITAT_ID", "hermes-local")
    job_id = _env("HABITAT_JOB_ID", "hermes-job")
    agent_id = _env("HABITAT_AGENT_ID", "hermes")
    secret = _env("HABITAT_AGENT_SECRET") or _env("HABITAT_WEBHOOK_SECRET")

    event_type = "job.completed" if args.status == "ok" else "job.failed"
    event = build_event(
        event_type=event_type,
        habitat_id=habitat_id or "hermes-local",
        job_id=job_id or "hermes-job",
        run_id=args.run_id,
        agent_id=agent_id,
        error=args.error,
    )
    body = json.dumps(event, separators=(",", ":"), sort_keys=True).encode()

    result: dict = {"event": event}

    if args.local_only or not secret:
        if args.prove and args.claim:
            try:
                result["local_proof"] = local_prove(
                    args.run_id,
                    args.claim,
                    "ok" if args.status == "ok" else "failed",
                    {"error": args.error} if args.error else None,
                )
            except Exception as e:
                result["local_proof_error"] = str(e)
                print(json.dumps(result, indent=2))
                return 1
        else:
            result["note"] = "No HABITAT_AGENT_SECRET set and --prove not requested; event not sent."
        print(json.dumps(result, indent=2))
        return 0

    events_url = args.url.rstrip("/") + "/events"
    try:
        result["ingest"] = post_signed(events_url, body, secret, agent_id)
    except SystemExit as e:
        result["ingest_error"] = str(e)
        print(json.dumps(result, indent=2))
        return 1

    if args.claim:
        claim_event = build_event(
            event_type="claim.submitted",
            habitat_id=habitat_id or "hermes-local",
            job_id=job_id or "hermes-job",
            run_id=args.run_id,
            agent_id=agent_id,
            claim=args.claim,
        )
        claim_body = json.dumps(claim_event, separators=(",", ":"), sort_keys=True).encode()
        try:
            result["claim_ingest"] = post_signed(events_url, claim_body, secret, agent_id)
        except SystemExit as e:
            result["claim_ingest_error"] = str(e)

    if args.prove and args.claim:
        try:
            # Prefer local export after HTTP ingest so the proof is available offline.
            result["local_proof"] = local_prove(
                args.run_id,
                args.claim,
                "ok" if args.status == "ok" else "failed",
                {"source": "hermes_hmac_adapter", "error": args.error},
            )
        except Exception as e:
            result["local_proof_error"] = str(e)

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
