#!/usr/bin/env python3
"""Verify a Habitat proof tip against the proof content hash."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: verify_tip.py PROOF_JSON TIP_JSON", file=sys.stderr)
        return 2

    proof_path = Path(sys.argv[1])
    tip_path = Path(sys.argv[2])

    with proof_path.open(encoding="utf-8") as handle:
        proof = json.load(handle)
    with tip_path.open(encoding="utf-8") as handle:
        tip = json.load(handle)

    expected = tip.get("tip")
    actual = proof.get("content_sha256")

    if not expected or expected != actual:
        print(f"TIP MISMATCH: expected={expected!r} actual={actual!r}", file=sys.stderr)
        return 1

    print("TIP OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
