# Habitat Examples

These examples show the intended adoption path: keep your existing agent stack, feed accountability-relevant events into Habitat, verify claims, and exchange portable proofs.

## 1. Quick start — local supervision

```bash
# Initialize from a minimal config
habitat init --config examples/simple.yaml

# Run the configured jobs once
habitat run

# Or run continuously
habitat run --watch --interval 10

# Inspect status
habitat status

# Generate a human-readable supervision dashboard
habitat generate -o dashboard.html
```

`examples/simple.yaml` defines a small demo habitat with a few scheduled jobs.

## 2. Submit a signed event

Start the Habitat HTTP server in one terminal:

```bash
export HABITAT_WEBHOOK_SECRET="dev-secret-change-me"
habitat serve --host 127.0.0.1 --port 8787
```

In another terminal:

```bash
export HABITAT_WEBHOOK_SECRET="dev-secret-change-me"
python examples/send_event.py http://127.0.0.1:8787
```

See `PROTOCOL.md` for the full event schema and required signature format.

## 3. OpenTelemetry bridge

```bash
python examples/otel_bridge.py
```

This shows how to project existing OTel-style GenAI spans into Habitat events while reusing the original `trace_id` as the Habitat `run_id`. The bridge is intentionally dependency-free.

## 4. Portable proof exchange (core differentiator)

### Producer side

After a claim has been verified:

```bash
habitat proof <claim-id> --output proof.json
```

This writes **only** the portable proof bundle.

### Consumer side (zero install)

Copy `tools/verify_proof.py` and the `proof.json` to any machine that has Python 3.10+:

```bash
python tools/verify_proof.py proof.json
```

### Consumer side (with Habitat installed)

```bash
python examples/proof_exchange.py proof.json
```

A valid proof establishes structural validity, content integrity, and internal claim/ledger consistency. It does **not** automatically prove publisher identity or external-world truth. See `VERIFY_PROOF.md`, `SECURITY.md`, and `ADOPTION.md` for the full assurance model.

## 5. Full end-to-end flow

See `examples/full_proof_flow.py` for a self-contained demonstration that:

1. Creates a habitat and records actions
2. Submits and verifies a claim
3. Exports a portable proof
4. Verifies the proof with the standalone verifier

## Further reading

- `ADOPTION.md` — how Habitat is intended to sit beside existing agent stacks
- `PROTOCOL.md` — event format and signing rules
- `ARCHITECTURE.md` — runtime boundaries
- `SECURITY.md` — threat model and explicit non-goals
- `PROOF.md` / `VERIFY_PROOF.md` — proof contract and verification semantics
