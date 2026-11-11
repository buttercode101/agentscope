from pathlib import Path
from habitat.anchor import tip_digest, write_tip_file, read_tip_file, check_tip


def test_tip_roundtrip(tmp_path: Path):
    proof = {"content_sha256": "a" * 64, "claim": {"id": "c1"}, "ledger": {"actions": []}}
    tip = tip_digest(proof)
    assert tip == "a" * 64
    path = write_tip_file(tip, tmp_path / "tip.json", claim_id="c1", run_id="r1")
    loaded = read_tip_file(path)
    assert loaded["tip"] == tip
    assert loaded["claim_id"] == "c1"
    result = check_tip(proof, path)
    assert result["match"] is True


def test_tip_mismatch(tmp_path: Path):
    write_tip_file("b" * 64, tmp_path / "tip.json")
    proof = {"content_sha256": "a" * 64}
    result = check_tip(proof, tmp_path / "tip.json")
    assert result["match"] is False
