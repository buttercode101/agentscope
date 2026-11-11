"""Minimal proof exchange demo.

Consumer side verifies a Habitat proof bundle from a local JSON file without
accessing the producer's Habitat database or network service. The verifier
uses only the proof bundle and Habitat's standalone proof-verification module.

Usage:
    python examples/proof_exchange.py proof.json
"""
from __future__ import annotations

import json
import sys

from habitat.proof_verify import verify_file


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python examples/proof_exchange.py proof.json", file=sys.stderr)
        return 2

    result = verify_file(sys.argv[1])
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
