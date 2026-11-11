"""Optional Ed25519 signing for portable Habitat proof bundles.

Signing is intentionally optional so the core runtime remains dependency-free.
Install the ``signing`` extra to use this module. Signatures authenticate the
proof bundle bytes; they do not prove that the underlying claim is true.
"""
from __future__ import annotations
import base64, copy, json
from typing import Any


def _canonical(value: dict[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def _unsigned(bundle: dict[str, Any]) -> dict[str, Any]:
    value = copy.deepcopy(bundle)
    value.pop("signature", None)
    return value


def _crypto():
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
        from cryptography.hazmat.primitives import serialization
        return Ed25519PrivateKey, Ed25519PublicKey, serialization
    except ImportError as exc:
        raise RuntimeError("Proof signing requires the optional 'signing' dependency: pip install 'habitat[signing]'") from exc


def generate_keypair() -> tuple[str, str]:
    Ed25519PrivateKey, _, serialization = _crypto()
    private = Ed25519PrivateKey.generate()
    private_raw = private.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
    public_raw = private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return base64.b64encode(private_raw).decode(), base64.b64encode(public_raw).decode()


def sign_proof(bundle: dict[str, Any], private_key_b64: str, key_id: str | None = None, agent_id: str | None = None) -> dict[str, Any]:
    """Return a signed copy of a proof bundle, optionally bound to an agent ID."""
    Ed25519PrivateKey, _, serialization = _crypto()
    try:
        private_raw = base64.b64decode(private_key_b64, validate=True)
    except Exception as exc:
        raise ValueError("Invalid base64 Ed25519 private key") from exc
    if len(private_raw) != 32:
        raise ValueError("Ed25519 private key must be 32 raw bytes")
    signer = Ed25519PrivateKey.from_private_bytes(private_raw)
    unsigned = _unsigned(bundle)
    signature = signer.sign(_canonical(unsigned))
    public_raw = signer.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    signed = copy.deepcopy(unsigned)
    signed["signature"] = {
        "algorithm": "Ed25519",
        "key_id": key_id,
        "agent_id": agent_id,
        "public_key": base64.b64encode(public_raw).decode(),
        "signature": base64.b64encode(signature).decode(),
    }
    return signed


def verify_signed_proof(bundle: dict[str, Any]) -> bool:
    """Verify a signed proof's embedded public key and signature."""
    _, Ed25519PublicKey, _ = _crypto()
    signature = bundle.get("signature")
    if not isinstance(signature, dict) or signature.get("algorithm") != "Ed25519":
        return False
    try:
        public_raw = base64.b64decode(signature["public_key"], validate=True)
        sig_raw = base64.b64decode(signature["signature"], validate=True)
        if len(public_raw) != 32 or len(sig_raw) != 64:
            return False
        Ed25519PublicKey.from_public_bytes(public_raw).verify(sig_raw, _canonical(_unsigned(bundle)))
        return True
    except Exception:
        # cryptography raises InvalidSignature for a tampered bundle. Treat all
        # malformed/invalid signatures as a clean verification failure.
        return False
