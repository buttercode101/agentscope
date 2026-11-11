import json
from pathlib import Path

import habitat.__main__ as cli


def test_proof_command_exports_only_portable_bundle(tmp_path: Path, monkeypatch):
    proof = {
        "proof_version": "1",
        "claim": {"status": "verified"},
        "ledger": {"integrity": "intact", "actions": []},
        "content_sha256": "abc",
    }

    class FakeStore:
        def __init__(self, _db):
            pass

        def close(self):
            pass

    monkeypatch.setattr(cli, "Store", FakeStore)
    monkeypatch.setattr(cli, "proof_status", lambda _store, _id: {
        "claim_id": "c1",
        "verdict": "verified",
        "ledger_integrity": "intact",
        "content_sha256": "abc",
        "proof": proof,
    })

    output = tmp_path / "proof.json"
    assert cli.main(["--db", str(tmp_path / "db.sqlite"), "proof", "c1", "-o", str(output)]) == 0
    assert json.loads(output.read_text(encoding="utf-8")) == proof


def test_proof_command_can_sign_without_putting_key_on_command_line(tmp_path: Path, monkeypatch):
    proof = {
        "proof_version": "1",
        "claim": {"status": "verified"},
        "ledger": {"integrity": "intact", "actions": []},
        "content_sha256": "abc",
    }
    signed = {**proof, "signature": {"algorithm": "Ed25519", "key_id": "k1", "agent_id": "a1"}}

    class FakeStore:
        def __init__(self, _db):
            pass

        def close(self):
            pass

    monkeypatch.setattr(cli, "Store", FakeStore)
    monkeypatch.setattr(cli, "proof_status", lambda _store, _id: {"proof": proof})
    monkeypatch.setattr(cli, "sign_proof", lambda bundle, key, key_id, agent_id: signed)
    monkeypatch.setenv("TEST_HABITAT_SIGNING_KEY", "secret-material")

    output = tmp_path / "signed-proof.json"
    assert cli.main([
        "--db", str(tmp_path / "db.sqlite"), "proof", "c1", "-o", str(output),
        "--signing-key-env", "TEST_HABITAT_SIGNING_KEY", "--key-id", "k1", "--agent-id", "a1",
    ]) == 0
    assert json.loads(output.read_text(encoding="utf-8")) == signed
