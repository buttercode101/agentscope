# Proof exchange

Habitat proof bundles are designed to cross system boundaries.

1. A producer exports `proof.json` from its Habitat runtime.
2. The producer sends that file to a consumer, CI job, auditor, or another agent.
3. The consumer runs:

```bash
python examples/proof_exchange.py proof.json
```

The verifier does **not** need the producer's database or runtime state. It checks the proof's digest and internal claim/ledger relationships.

A valid result means the bundle is internally consistent and has not changed since its digest was generated. It does **not** by itself establish external-world truth or publisher identity. For signed proofs, use the signing/trust verification path described in `SIGNING.md`.

This example is intentionally tiny: it demonstrates the interoperability primitive without introducing a service, dashboard, hosted dependency, or new protocol layer.
