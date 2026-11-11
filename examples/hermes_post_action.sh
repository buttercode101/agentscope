#!/usr/bin/env bash
# Example Hermes post-action wrapper.
# Call after a scheduled job finishes. Secrets via env only.
set -euo pipefail
RUN_ID="${1:-hermes-$(date -u +%Y%m%dT%H%M%SZ)}"
STATUS="${2:-ok}"
CLAIM="${3:-Hermes job completed}"
export HABITAT_HABITAT_ID="${HABITAT_HABITAT_ID:-hermes-local}"
export HABITAT_JOB_ID="${HABITAT_JOB_ID:-hermes-job}"
export HABITAT_AGENT_ID="${HABITAT_AGENT_ID:-hermes}"
# HABITAT_AGENT_SECRET must be set in the environment / secrets manager
python "$(dirname "$0")/hermes_hmac_adapter.py" \
  --run-id "$RUN_ID" \
  --status "$STATUS" \
  --claim "$CLAIM" \
  --prove
