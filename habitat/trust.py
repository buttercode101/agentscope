"""Small trust registry for signed proof verification.

A valid Ed25519 signature is not treated as trusted until its key ID and public
key are present in the caller's registry. An embedded agent ID is only trusted
when the registry explicitly binds that key to the same agent.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from .proof_sign import verify_signed_proof


@dataclass(frozen=True)
class TrustedKey:
    key_id: str
    public_key: str
    agent_id: str | None = None
    expires_at: datetime | None = None
    enabled: bool = True


class TrustRegistry:
    def __init__(self, keys: Iterable[TrustedKey] = ()):
        self._keys = {key.key_id: key for key in keys}

    def add(self, key: TrustedKey) -> None:
        self._keys[key.key_id] = key

    def revoke(self, key_id: str) -> None:
        key = self._keys.get(key_id)
        if key:
            self._keys[key_id] = TrustedKey(key.key_id, key.public_key, key.agent_id, key.expires_at, False)

    def get(self, key_id: str) -> TrustedKey | None:
        return self._keys.get(key_id)

    def is_trusted(self, key_id: str, public_key: str, now: datetime | None = None, agent_id: str | None = None) -> bool:
        key = self._keys.get(key_id)
        if not key or not key.enabled or key.public_key != public_key:
            return False
        # If a caller wants attribution to an agent, the trust anchor must bind
        # that key to the same agent. An unbound key authenticates only the key,
        # not an arbitrary identity string carried by the proof.
        if key.agent_id is None:
            if agent_id is not None:
                return False
        elif key.agent_id != agent_id:
            return False
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None or current.utcoffset() is None:
            current = current.replace(tzinfo=timezone.utc)
        expiry = key.expires_at
        if expiry is None:
            return True
        if expiry.tzinfo is None or expiry.utcoffset() is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        return current < expiry

    def verify(self, bundle: dict, now: datetime | None = None, agent_id: str | None = None) -> bool:
        signature = bundle.get("signature")
        if not isinstance(signature, dict):
            return False
        key_id = signature.get("key_id")
        public_key = signature.get("public_key")
        signed_agent = signature.get("agent_id")
        if agent_id is not None and signed_agent != agent_id:
            return False
        # A proof that carries an agent identity must have that identity bound by
        # the trust anchor; otherwise the identity would be unauthenticated
        # metadata even though the signature itself is valid.
        expected_agent = agent_id if agent_id is not None else signed_agent
        if signed_agent is not None and expected_agent is None:
            return False
        return bool(key_id and public_key and self.is_trusted(key_id, public_key, now, expected_agent) and verify_signed_proof(bundle))
