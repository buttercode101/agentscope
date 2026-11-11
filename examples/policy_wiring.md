# Policy wiring for Hermes / agentscope failure modes

Use `habitat.policy_presets` when verifying claims that must not accept
drift skips, auth failures, or stale evidence.

```python
from habitat.policy_presets import PRESETS
from habitat.policy import apply_policy
from habitat.verify import verify_claim

claim = store.get_claim(claim_id)
verify_claim(store, claim)
claim = store.get_claim(claim_id)  # refresh evidence

policy = PRESETS["no_drift_skip"]()
decision = apply_policy(policy, claim.evidence or {})
if decision["status"] != "allowed":
    # raise supervision signal / reject claim export
    print("policy denied:", decision["reasons"])
```

Presets:

| Name | Intent |
|------|--------|
| `trusted_ledger_with_run` | Evidence must come from Habitat ledger and carry a run_id |
| `no_drift_skip` | Require status=ok (pair with agentscope drift detection) |
| `auth_ok` | Same, oriented at auth failure streaks |
| `recent_action` | Reject evidence older than max_age_seconds (default 1h) |

These policies never invent evidence; they only constrain what verification already returned.
