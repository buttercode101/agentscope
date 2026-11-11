"""Optional external tip anchoring for Habitat proofs.

Local SHA-256 chains are tamper-evident within the producer's database.
An external tip raises the bar against whole-ledger rewrite by recording the
current tip digest outside the Habitat database (git notes, a tip file, or a
simple public location). This module stays local-first and optional.

Habitat still does not claim external-world truth or remote attestation.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def tip_digest(proof_or_ledger: dict[str, Any]) -> str:
    """Compute a stable tip digest from a proof bundle or a ledger object."""
    if "content_sha256" in proof_or_ledger and isinstance(proof_or_ledger["content_sha256"], str):
        return proof_or_ledger["content_sha256"]
    actions = []
    if isinstance(proof_or_ledger.get("ledger"), dict):
        actions = proof_or_ledger["ledger"].get("actions") or []
    elif isinstance(proof_or_ledger.get("actions"), list):
        actions = proof_or_ledger["actions"]
    payload = json.dumps(actions, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def write_tip_file(
    tip: str,
    path: str | Path,
    *,
    claim_id: str | None = None,
    run_id: str | None = None,
    proof_path: str | None = None,
) -> Path:
    """Write a small tip record that a verifier or human can inspect later."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "habitat_tip_version": 1,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "tip": tip,
        "claim_id": claim_id,
        "run_id": run_id,
        "proof_path": proof_path,
    }
    out.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out


def read_tip_file(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("habitat_tip_version") != 1:
        raise ValueError("not a Habitat tip file")
    if not isinstance(data.get("tip"), str) or len(data["tip"]) != 64:
        raise ValueError("tip digest missing or malformed")
    return data


def check_tip(proof: dict[str, Any], tip_path: str | Path) -> dict[str, Any]:
    """Compare a proof's content digest against an external tip file."""
    expected = read_tip_file(tip_path)
    actual = proof.get("content_sha256")
    match = isinstance(actual, str) and actual == expected["tip"]
    return {
        "match": match,
        "expected_tip": expected["tip"],
        "actual_tip": actual,
        "tip_file": str(tip_path),
        "recorded_at": expected.get("recorded_at"),
    }
